# {{DESCRIPTION}}
# Generated from the nx12-modeling conservative Journal template.
#
# SCAFFOLD. The control flow below is complete, but the modeling body is not:
# implement one small, version-verified operation before this journal does
# anything useful. A scaffold is not a working journal.
#
# Failure-handling contract, and why each part is written the way it is:
#
#   * log() never raises, so a diagnostic that fails cannot hide the failure
#     it was reporting.
#   * log_safely() guards the call itself, so even a broken log() cannot
#     prevent cleanup or rollback.
#   * destroy_builders() never raises and never lets one failed Destroy() skip
#     the remaining builders.
#   * undo_to_mark() never raises, so a failed rollback cannot replace the
#     original operation exception.
#   * The cleanup and rollback calls in main() are guarded as well. The
#     original exception is the one that reaches the caller, always.
#
# Ordering: builders are destroyed first, then the undo mark is restored. Every
# builder here is created after the undo mark, so rolling back first could
# invalidate the very objects cleanup still has to release.
#
# Ownership: only builders created by this journal are destroyed. Committed
# results belong to the model. The session and the work part are never
# destroyed, and UndoMarkId is a value rather than a resource.

import sys
import traceback

import NXOpen


JOURNAL_NAME = "{{JOURNAL_NAME}}"

_session = None


def log(message):
    """Report a diagnostic without ever raising."""
    text = str(message)
    try:
        sys.stderr.write(text + "\n")
    except Exception:
        pass
    if _session is None:
        return
    try:
        window = _session.ListingWindow
        window.Open()
        window.WriteLine(text)
    except Exception:
        # The Listing Window is optional; the stderr line above already
        # carried the message, so losing this copy is not fatal.
        pass


def log_safely(message):
    """Call log() defensively.

    log() is already written not to raise, but cleanup and rollback must not
    depend on that remaining true. Guarding here keeps a future edit to log()
    from being able to strand a failed journal.
    """
    try:
        log(message)
    except Exception:
        pass


def register_builder(builders, builder):
    """Record a builder the moment it exists, so cleanup cannot miss it."""
    builders.append(builder)
    return builder


def destroy_builders(builders):
    """Release every builder this journal owns. Never raises."""
    while builders:
        builder = builders.pop()
        try:
            builder.Destroy()
        except Exception:
            log_safely(
                "A builder could not be destroyed cleanly:\n"
                + traceback.format_exc()
            )


def undo_to_mark(session, undo_mark):
    """Restore the undo mark. Never raises, so it cannot mask the real error."""
    try:
        session.UndoToMark(undo_mark, JOURNAL_NAME)
    except Exception:
        log_safely(
            "Rollback to the journal undo mark failed:\n" + traceback.format_exc()
        )


def run_modeling(session, work_part, builders):
    """Do the journal's actual work. Raise on failure, return None on success.

    UNVERIFIED: this body is a placeholder. Replace it with one small,
    version-verified operation before running the journal against a part.
    """
    # Add an evidence comment beside each nontrivial call. The comment begins
    # with the evidence marker, then the member path, then the fields that
    # references/api-validation.md defines, separated by "|":
    #
    #     <marker> <NXOpen.Member.Path> | source=<source> | file=<index>
    #              | version=<x.y.z> | binding=<dotnet|python>
    #
    # A call verified against this installation would therefore carry its
    # member path along with source=local-xml, file=NXBIN/managed/NXOpen.xml,
    # version=12.0.0.27 and binding=dotnet.
    #
    # The literal marker is spelled out in references/api-validation.md. It is
    # left out here so that an unfilled scaffold does not carry a comment that
    # looks like real evidence.
    #
    # Register a builder as soon as it is created:
    #
    #   builder = register_builder(builders, collection.CreateXxxBuilder(None))
    #
    log_safely(JOURNAL_NAME + ": scaffold only; no modeling operation is configured.")


def main():
    global _session

    _session = session = NXOpen.Session.GetSession()
    work_part = session.Parts.Work
    if work_part is None:
        raise RuntimeError(
            "Open a disposable NX 12 work part before running this journal."
        )

    builders = []
    rollback_needed = False

    undo_mark = session.SetUndoMark(
        NXOpen.Session.MarkVisibility.Visible,
        JOURNAL_NAME,
    )

    try:
        run_modeling(session, work_part, builders)
    except BaseException:
        rollback_needed = True
        log_safely(traceback.format_exc())
        # Bare raise keeps the original exception and its traceback. The
        # finally block runs first and is written so that nothing it does can
        # displace this exception.
        raise
    finally:
        try:
            destroy_builders(builders)
        except BaseException:
            pass
        if rollback_needed:
            try:
                undo_to_mark(session, undo_mark)
            except BaseException:
                pass

    # No save, Save As, close, delete, export, or submit happens here on
    # purpose. Add those only when the user has explicitly asked for the
    # operation and the destination.
    return 0


if __name__ == "__main__":
    main()
