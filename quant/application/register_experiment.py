from dataclasses import dataclass

from quant.domain import Experiment
from quant.ports import ExperimentRepository


@dataclass(frozen=True, slots=True)
class RegisterExperiment:
    repository: ExperimentRepository

    def __call__(self, experiment: Experiment) -> None:
        self.repository.add(experiment)
