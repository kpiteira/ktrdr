"""Tests for brief translator — genome to design prompt conversion."""

from __future__ import annotations

from datetime import date

from ktrdr.evolution.brief import BriefTranslator
from ktrdr.evolution.config import DateRange, EvolutionConfig
from ktrdr.evolution.genome import Genome, TraitLevel


class TestBriefTranslator:
    """Tests for BriefTranslator.translate()."""

    def _make_config(self) -> EvolutionConfig:
        """Helper to create a config with known values."""
        return EvolutionConfig(
            symbol="EURUSD",
            timeframe="1h",
            training_window=DateRange(
                start=date(2015, 1, 1), end=date(2020, 12, 31)
            ),
            fitness_slices=[
                DateRange(start=date(2021, 1, 1), end=date(2022, 6, 30)),
                DateRange(start=date(2022, 7, 1), end=date(2023, 12, 31)),
                DateRange(start=date(2024, 1, 1), end=date(2025, 6, 30)),
            ],
        )

    def test_all_27_genomes_produce_nonempty_briefs(self) -> None:
        """Every genome should produce a non-empty brief."""
        config = self._make_config()
        translator = BriefTranslator()
        for genome in Genome.all_combinations():
            brief = translator.translate(genome, config)
            assert brief.strip(), f"Empty brief for {genome}"

    def test_all_27_briefs_are_unique(self) -> None:
        """No two genomes should produce identical briefs."""
        config = self._make_config()
        translator = BriefTranslator()
        briefs = [translator.translate(g, config) for g in Genome.all_combinations()]
        assert len(set(briefs)) == 27

    def test_brief_contains_training_window(self) -> None:
        """Brief should include training window dates."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config)
        assert "2015-01-01" in brief
        assert "2020-12-31" in brief

    def test_brief_contains_backtest_window(self) -> None:
        """Brief should include the first fitness slice as backtest window."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config)
        assert "2021-01-01" in brief
        assert "2022-06-30" in brief

    def test_brief_contains_symbol_and_timeframe(self) -> None:
        """Brief should include the configured symbol and timeframe."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config)
        assert "EURUSD" in brief
        assert "1h" in brief

    def test_novelty_off_brief(self) -> None:
        """novelty=OFF should mention systematic or proven patterns."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.OFF,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config).lower()
        assert "systematic" in brief or "proven" in brief

    def test_novelty_high_brief(self) -> None:
        """novelty=HIGH should mention creative or experimental or unusual."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.HIGH,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config).lower()
        assert "creative" in brief or "experimental" in brief or "unusual" in brief

    def test_skepticism_high_brief(self) -> None:
        """skepticism=HIGH should mention conservative or maximum 2 indicators."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.HIGH,
            memory_depth=TraitLevel.LOW,
        )
        brief = translator.translate(genome, config).lower()
        assert "conservative" in brief or "maximum 2 indicators" in brief

    def test_memory_off_brief(self) -> None:
        """memory=OFF should mention ignore or fresh."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.OFF,
        )
        brief = translator.translate(genome, config).lower()
        assert "ignore" in brief or "fresh" in brief

    def test_memory_high_brief(self) -> None:
        """memory=HIGH should mention synthesize or all experiment history."""
        config = self._make_config()
        translator = BriefTranslator()
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.HIGH,
        )
        brief = translator.translate(genome, config).lower()
        assert "synthesize" in brief or "all experiment history" in brief
