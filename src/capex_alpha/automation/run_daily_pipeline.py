"""Daily pipeline — orchestrates v2 modules end-to-end.

Importable as ``run_pipeline()``; CLI entrypoint lives in
``scripts/run_daily_pipeline.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .. import data_loader as _dl
from ..dashboard import daily_report_generator as drg
from ..dashboard import dashboard_data as dd
from ..fusion import alpha_ranking as ar
from ..fusion import scoring_model_v2 as sm
from ..narrative import capex_interpreter as ci
from ..narrative import narrative_scorer as ns
from ..narrative import news_parser as np_mod
from ..quant import ai_factor_index as afi
from ..quant import factor_model_v2 as fm
from ..quant import regime_filter as rf
from ..quant import residual_alpha as ra
from ..quant import risk_model as rm
from ..utils import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    ai_index: pd.DataFrame = field(default_factory=pd.DataFrame)
    residual: pd.DataFrame = field(default_factory=pd.DataFrame)
    regime: pd.DataFrame = field(default_factory=pd.DataFrame)
    factors: pd.DataFrame = field(default_factory=pd.DataFrame)
    capex_context: pd.DataFrame = field(default_factory=pd.DataFrame)
    news: pd.DataFrame = field(default_factory=pd.DataFrame)
    narrative: pd.DataFrame = field(default_factory=pd.DataFrame)
    risk: pd.DataFrame = field(default_factory=pd.DataFrame)
    ranking: pd.DataFrame = field(default_factory=pd.DataFrame)
    payload: dict = field(default_factory=dict)
    report: str = ""


def run_pipeline(
    write: bool = True,
    skip_fetch: bool = False,
    as_of: pd.Timestamp | None = None,
) -> PipelineResult:
    """End-to-end daily pipeline. Returns all intermediate artifacts.

    ``skip_fetch=True`` forces every yfinance loader call in this run to use
    the on-disk cache regardless of staleness — useful for offline/dev work.
    Default is ``False`` (refresh stale caches via yfinance, fall back to
    stale cache only if fetch fails). The flag is plumbed through the process-
    wide override on ``capex_alpha.data_loader``.
    """
    res = PipelineResult()
    _prev_override = _dl._CACHE_MAX_AGE_DAYS_OVERRIDE
    if skip_fetch:
        _dl.set_cache_max_age_override(10**9)
    try:
        return _run_pipeline_body(res, write=write, as_of=as_of)
    finally:
        _dl.set_cache_max_age_override(_prev_override)


def _run_pipeline_body(
    res: PipelineResult,
    write: bool,
    as_of: pd.Timestamp | None,
) -> PipelineResult:
    logger.info("[1/9] Building AI factor index …")
    res.ai_index = afi.run(write=write)

    logger.info("[2/9] Computing residual alpha …")
    res.residual = ra.run(write=write, ai_index_df=res.ai_index)

    logger.info("[3/9] Running regime filter …")
    res.regime = rf.run(write=write, ai_index_df=res.ai_index)

    logger.info("[4/9] Building factor model v2 …")
    res.factors = fm.run(write=write, residual_df=res.residual, ai_index_df=res.ai_index)

    logger.info("[5/9] Interpreting CAPEX context …")
    res.capex_context = ci.run(write=write)

    logger.info("[6/9] Parsing news → narrative signals …")
    res.news = np_mod.run(write=write, as_of=as_of)
    res.narrative = ns.run(write=write, news_signals=res.news, capex_context=res.capex_context, as_of=as_of)

    logger.info("[7/9] Computing risk flags …")
    res.risk = rm.run(write=write, residual_df=res.residual)

    logger.info("[8/9] Scoring + ranking …")
    res.ranking = sm.run(
        write=write,
        factor_df=res.factors,
        narrative_df=res.narrative,
        risk_df=res.risk,
        regime_df=res.regime,
        residual_df=res.residual,
    )
    ar.run(write=write, ranking=res.ranking)

    logger.info("[9/9] Building dashboard + daily report …")
    res.payload = dd.run(
        write=write,
        ranking=res.ranking,
        regime=res.regime,
        ai_index=res.ai_index,
        capex_context=res.capex_context,
    )
    res.report = drg.run(write=write, payload=res.payload)

    logger.info("Daily pipeline complete.")
    return res
