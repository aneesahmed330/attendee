from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bots.models import BotEvent, BotEventTypes

# techverx-server runs bot concurrency capped at 2 against a measured real
# peak of 6 simultaneous meetings (see server-migrate-plan.md §3f/§4h). A bot
# beyond that cap queues in the celery "bots" queue and joins late rather
# than never — this command is the concrete, day-to-day measurement of how
# often and how late that actually happens, so raising RAM/concurrency later
# is a data-driven decision instead of a guess.
LATE_THRESHOLD = timedelta(minutes=5)

# Bounds query cost only, not correctness: correctness comes from the
# "late_join_checked" metadata marker below, so an event is reported exactly
# once no matter how often (or rarely) this command runs. Without the marker,
# running this every minute via cron would print the same late join dozens of
# times over — once per run until the event aged out of a lookback window.
LOOKBACK = timedelta(hours=24)


class Command(BaseCommand):
    help = "Log bots that joined their meeting more than LATE_THRESHOLD after their scheduled join_at. Safe to run every minute via cron — each BotEvent is only ever reported once."

    def handle(self, *args, **options):
        cutoff = timezone.now() - LOOKBACK
        events = (
            BotEvent.objects.filter(event_type=BotEventTypes.BOT_JOINED_MEETING, created_at__gte=cutoff)
            .exclude(metadata__late_join_checked=True)
            .select_related("bot")
        )

        for event in events:
            bot = event.bot
            if bot.join_at:
                delay = event.created_at - bot.join_at
                if delay > LATE_THRESHOLD:
                    self.stdout.write(
                        f"{timezone.now().isoformat()} LATE_JOIN bot={bot.object_id} meeting={bot.name!r} "
                        f"join_at={bot.join_at.isoformat()} joined_at={event.created_at.isoformat()} "
                        f"delay_seconds={int(delay.total_seconds())}"
                    )
            # Mark examined regardless of outcome so this event (late or not)
            # is never re-checked — this is what makes repeated cron runs safe.
            event.metadata = {**event.metadata, "late_join_checked": True}
            event.save(update_fields=["metadata"])
