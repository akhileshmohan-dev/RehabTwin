from datetime import datetime
from .thread import DigitalThread


def format_number(value, decimals=1):
    if value is None:
        return "--"
    return f"{value:.{decimals}f}"


def format_datetime(value):
    if not value:
        return "--"

    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d-%b-%Y %H:%M")
    except ValueError:
        return str(value)


def print_report():
    thread = DigitalThread()

    # Get all sessions directly through SQLAlchemy
    with thread.db.session() as db:
        from .models import Session

        sessions = (
            db.query(Session)
            .order_by(Session.started_at.desc())
            .all()
        )

        print()
        print("=" * 100)
        print("                      REHABTWIN SESSION HISTORY")
        print("=" * 100)

        if not sessions:
            print("\nNo rehabilitation sessions found.")
            print("=" * 100)
            return

        for index, session in enumerate(sessions, start=1):

            print(f"\nSession {index}")
            print("-" * 100)

            print(f"Patient ID     : {session.patient_id}")
            print(f"Session ID     : {session.session_id}")
            print(f"Exercise       : {session.exercise}")
            print(f"Started        : {format_datetime(session.started_at.isoformat())}")
            print(
                f"Ended          : "
                f"{format_datetime(session.ended_at.isoformat()) if session.ended_at else '--'}"
            )
            print(f"Status         : {session.status}")

            if not session.results:
                print("\nResult         : No result recorded.")
                continue

            for result_number, result in enumerate(session.results, start=1):

                print(f"\nResult {result_number}")
                print(f"  Repetitions  : {result.repetitions} reps")

                print(
                    f"  ROM Minimum  : "
                    f"{format_number(result.rom_min)} deg"
                )

                print(
                    f"  ROM Maximum  : "
                    f"{format_number(result.rom_max)} deg"
                )

                print(
                    f"  Average ROM  : "
                    f"{format_number(result.rom_average)} deg"
                )

                if result.performance_score is not None:
                    print(
                        f"  Score        : "
                        f"{format_number(result.performance_score)} %"
                    )
                else:
                    print("  Score        : --")

                print(
                    f"  Feedback     : "
                    f"{result.feedback or '--'}"
                )

        print("\n" + "=" * 100)
        print(f"Total Sessions: {len(sessions)}")
        print("=" * 100)


if __name__ == "__main__":
    print_report()