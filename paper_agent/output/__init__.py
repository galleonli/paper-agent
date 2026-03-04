# Output: local notes, daily digest, Slack

from paper_agent.output.local import write_local_note, write_daily_digest
from paper_agent.output.slack import send_slack_brief

__all__ = ["write_local_note", "write_daily_digest", "send_slack_brief"]
