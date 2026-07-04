"""GEPA optimizer — reflective prompt evolution via DSPy (the real upgrade).

DSPy's GEPA evolves an instruction/prompt from natural-language feedback on
execution traces, beating MIPROv2 and RL with far fewer rollouts. This wires it
to evolve agi-layer's system-prompt template from accumulated feedback. Requires
`pip install dspy-ai` and a configured LM; import-guards cleanly otherwise, so
the heuristic Optimizer stays the always-available default.

This is the real integration shape — supply `trainset` (dspy.Example objects
carrying your feedback traces) and point `reflection_model` at a strong model.
"""
from __future__ import annotations


class GEPAOptimizer:
    def __init__(self, *, reflection_model: str | None = None, auto: str = "light"):
        self.reflection_model = reflection_model
        self.auto = auto

    def available(self) -> bool:
        try:
            import dspy  # noqa: F401
            return True
        except Exception:
            return False

    def evolve_prompt(self, base_instruction: str, trainset) -> str:
        """Evolve `base_instruction` against feedback traces; return the best
        instruction found. Raises RuntimeError if DSPy isn't installed."""
        try:
            import dspy
            from dspy import GEPA
        except Exception as e:  # pragma: no cover - depends on install
            raise RuntimeError(
                "dspy-ai isn't installed — `pip install dspy-ai` to use GEPA."
            ) from e

        class _Turn(dspy.Signature):
            """Answer the user using retrieved memory."""
            question = dspy.InputField()
            answer = dspy.OutputField()

        program = dspy.Predict(_Turn)
        program.signature.instructions = base_instruction

        def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
            # Feedback-shaped metric: GEPA reflects on the natural-language
            # `feedback` string, not just the scalar score.
            return dspy.Prediction(
                score=float(getattr(gold, "score", 0.0) or 0.0),
                feedback=getattr(gold, "feedback", "") or "",
            )

        reflection_lm = dspy.LM(self.reflection_model) if self.reflection_model else None
        gepa = GEPA(metric=metric, auto=self.auto, reflection_lm=reflection_lm)
        optimized = gepa.compile(program, trainset=trainset, valset=trainset)
        return getattr(optimized.signature, "instructions", base_instruction)
