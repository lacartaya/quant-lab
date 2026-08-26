from dataclasses import dataclass
from datetime import datetime

from quant.application.dataset_snapshots import (
    CreateDatasetSnapshot,
    LoadDatasetSnapshot,
)
from quant.domain import AdjustmentPolicy, DatasetSnapshot, HistoricalDataRequest


@dataclass(frozen=True, slots=True)
class HistoricalDatasetImportResult:
    snapshot: DatasetSnapshot
    bar_count: int
    actual_start_at: datetime
    actual_end_at: datetime


@dataclass(frozen=True, slots=True)
class ImportHistoricalDataset:
    creator: CreateDatasetSnapshot
    loader: LoadDatasetSnapshot

    def execute(
        self,
        *,
        market: str,
        instrument: str,
        timeframe: str,
        start_at: datetime,
        end_at: datetime,
        adjustment_policy: AdjustmentPolicy,
    ) -> HistoricalDatasetImportResult:
        snapshot = self.creator(
            HistoricalDataRequest(
                market=market,
                instrument=instrument.upper(),
                timeframe=timeframe,
                start_at=start_at,
                end_at=end_at,
                adjustment_policy=adjustment_policy,
            )
        )
        dataset = self.loader(snapshot.id)
        return HistoricalDatasetImportResult(
            snapshot=snapshot,
            bar_count=len(dataset.bars),
            actual_start_at=dataset.bars[0].timestamp,
            actual_end_at=dataset.bars[-1].timestamp,
        )
