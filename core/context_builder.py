"""Context builder — assembles the final prompt from memory + session."""
from __future__ import annotations

from core.session import Session
from memory.schema import ContextBundle


class ContextBuilder:
    def build(self, session: Session, ctx: ContextBundle, model):
        """Compose the prompt sent to the model, in order:

          1. System instructions (who the layer is, the active scope).
          2. Retrieved memory block (ctx.items — already budget-packed).
          3. A one-line note of what was dropped (ctx.summary_of_dropped).
          4. Recent working-memory turns (session.recent()).
          5. The user's current input.

        Format to the target model's expected shape (a messages list, etc.).
        """
        raise NotImplementedError("Assemble the prompt; see ARCHITECTURE.md (Read path)")
