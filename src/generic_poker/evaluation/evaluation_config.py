"""Configuration loader for hand evaluation types."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DataFileConfig:
    """Configuration for a data file (ranking or description)."""

    source_type: str  # "csv", "database", "generated"
    path: str | None = None
    generator: str | None = None
    parameters: dict[str, Any] | None = None


@dataclass
class EvaluationConfig:
    """Configuration for a hand evaluation type."""

    id: str
    name: str
    description: str
    hand_size: int
    rank_order: str
    ranking_data: DataFileConfig
    description_data: DataFileConfig


class EvaluationConfigLoader:
    """Loads and manages hand evaluation configurations."""

    def __init__(self, config_dir: Path | None = None):
        """
        Initialize the loader.

        Args:
            config_dir: Directory containing evaluation JSON files.
                       Defaults to data/hand_evaluations from project root.
        """
        if config_dir is None:
            # Default to data/hand_evaluations from project root
            config_dir = Path(__file__).parents[3] / "data" / "hand_evaluations"

        self.config_dir = config_dir
        self._configs: dict[str, EvaluationConfig] = {}
        self._loaded = False

    def load_all_configs(self) -> None:
        """Load all evaluation configuration files from the directory."""
        if self._loaded:
            return

        logger.info(f"Loading evaluation configurations from {self.config_dir}")

        if not self.config_dir.exists():
            logger.error(f"Configuration directory not found: {self.config_dir}")
            raise FileNotFoundError(f"Configuration directory not found: {self.config_dir}")

        # Find all .json files in the directory
        json_files = list(self.config_dir.glob("*.json"))

        if not json_files:
            logger.warning(f"No JSON configuration files found in {self.config_dir}")
            return

        for json_file in json_files:
            try:
                eval_type = json_file.stem  # filename without extension
                config = self._load_config_file(json_file)
                self._configs[eval_type] = config
                logger.debug(f"Loaded configuration for {eval_type}")
            except Exception as e:
                logger.error(f"Failed to load configuration from {json_file}: {e}")
                continue

        logger.info(f"Loaded {len(self._configs)} evaluation configurations")
        self._loaded = True

    def _load_config_file(self, filepath: Path) -> EvaluationConfig:
        """Load a single evaluation configuration file."""
        with open(filepath) as f:
            data = json.load(f)

        # Parse data file configurations
        data_files = data.get("data_files", {})

        ranking_config = data_files.get("ranking", {})
        ranking_data = DataFileConfig(
            source_type=ranking_config.get("source_type", "csv"),
            path=ranking_config.get("path"),
            generator=ranking_config.get("generator"),
            parameters=ranking_config.get("parameters"),
        )

        description_config = data_files.get("description", {})
        description_data = DataFileConfig(
            source_type=description_config.get("source_type", "csv"),
            path=description_config.get("path"),
            generator=description_config.get("generator"),
            parameters=description_config.get("parameters"),
        )

        return EvaluationConfig(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            hand_size=data.get("hand_size", 5),
            rank_order=data.get("rank_order", "BASE_RANKS"),
            ranking_data=ranking_data,
            description_data=description_data,
        )

    def get_config(self, eval_type: str) -> EvaluationConfig | None:
        """
        Get configuration for a specific evaluation type.

        Args:
            eval_type: The evaluation type (e.g., 'high', 'a5_low')

        Returns:
            EvaluationConfig if found, None otherwise
        """
        if not self._loaded:
            self.load_all_configs()

        return self._configs.get(eval_type)

    def get_all_configs(self) -> dict[str, EvaluationConfig]:
        """Get all loaded configurations."""
        if not self._loaded:
            self.load_all_configs()

        return self._configs.copy()

    def get_hand_size(self, eval_type: str) -> int:
        """Get hand size for an evaluation type."""
        config = self.get_config(eval_type)
        return config.hand_size if config else 5  # Default to 5

    def get_rank_order(self, eval_type: str) -> str:
        """Get rank order constant name for an evaluation type."""
        config = self.get_config(eval_type)
        return config.rank_order if config else "BASE_RANKS"  # Default

    def get_ranking_file_path(self, eval_type: str) -> str | None:
        """Get the ranking file path for an evaluation type."""
        config = self.get_config(eval_type)
        if not config:
            return None

        if config.ranking_data.source_type in ["csv", "database"]:
            return config.ranking_data.path

        return None  # Generated data doesn't have a file path

    def get_description_file_path(self, eval_type: str) -> str | None:
        """Get the description file path for an evaluation type."""
        config = self.get_config(eval_type)
        if not config:
            return None

        if config.description_data.source_type == "csv":
            return config.description_data.path

        return None  # Generated data doesn't have a file path

    def is_generated_descriptions(self, eval_type: str) -> bool:
        """Check if descriptions are generated for an evaluation type."""
        config = self.get_config(eval_type)
        if not config:
            return False

        return config.description_data.source_type == "generated"

    def get_description_generator_config(self, eval_type: str) -> dict[str, Any] | None:
        """Get generator configuration for description generation."""
        config = self.get_config(eval_type)
        if not config or config.description_data.source_type != "generated":
            return None

        return {"generator": config.description_data.generator, "parameters": config.description_data.parameters or {}}


# Global instance
evaluation_config_loader = EvaluationConfigLoader()


def get_evaluation_config(eval_type: str) -> EvaluationConfig | None:
    """Convenience function to get evaluation configuration."""
    return evaluation_config_loader.get_config(eval_type)


def get_hand_size_for_type(eval_type: str) -> int:
    """Convenience function to get hand size for evaluation type."""
    return evaluation_config_loader.get_hand_size(eval_type)


def get_rank_order_for_type(eval_type: str) -> str:
    """Convenience function to get rank order for evaluation type."""
    return evaluation_config_loader.get_rank_order(eval_type)
