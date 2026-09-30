// {{DESCRIPTION}}
// Generated from the nx12-modeling conservative Journal template.
//
// SCAFFOLD. The control flow below is complete, but the modeling body is not:
// implement one small, version-verified operation before this journal does
// anything useful. A scaffold is not a working journal.
//
// Failure-handling contract, and why each part is written the way it is:
//
//   * Log() never throws, so a diagnostic that fails cannot hide the failure
//     it was reporting.
//   * DestroyBuilders() never throws and never lets one failed Destroy() skip
//     the remaining builders.
//   * UndoToMark() never throws, so a failed rollback cannot replace the
//     original operation exception.
//
// Ordering: builders are destroyed first, then the undo mark is restored. Every
// builder here is created after the undo mark, so rolling back first could
// invalidate the very objects cleanup still has to release.
//
// Ownership: only builders created by this journal are destroyed. Committed
// results belong to the model. The session, the work part, and the undo mark id
// are never destroyed by a journal -- UndoMarkId is a value, not a resource.
//
// Failure contract, stated once and relied on everywhere below:
//
//   * Success        Main returns 0.
//   * Failure        Run() destroys its builders, attempts to roll the part
//                    back to the undo mark, and rethrows the ORIGINAL
//                    exception with a bare "throw;", which preserves the
//                    exception object and its stack trace. Main catches that
//                    same object, reports it in full, and returns the
//                    documented nonzero code 1.
//   * No work part   Reported before the undo mark exists, so there is nothing
//                    to roll back. Main still returns 1.
//
//   The original exception is never replaced by a cleanup, rollback or logging
//   failure, because none of those three helpers can throw. Main is the only
//   place that reports a failure, so every failure path is reported exactly
//   once, in full, and after cleanup has already finished.
//
// Rollback status, and why it is recorded instead of assumed:
//
//   A failure can happen before the undo mark exists at all, and the restore
//   itself can fail. "The part was rolled back" is therefore true in only one
//   of three cases, so the outcome is recorded as it happens and Main reports
//   the recorded value:
//
//     not-attempted  no UndoToMark call was made -- for example the journal
//                    failed before the undo mark was created
//     succeeded      UndoToMark was called and returned normally
//     failed         UndoToMark was called and threw
//
//   A rollback exception is kept separately and reported as a second, clearly
//   labelled message. It never replaces the original failure.
//
// Nothing here saves, closes, overwrites, exports or submits the part. Do not
// add those unless the user explicitly asked for the operation and destination.
//
// Target: NX 12 (verified against NX 12.0.0.27). Binding=dotnet, C# 5.
// Compile check: scripts/validate-nx12-csharp.ps1 -SourceFile <this file>
//   -NxRoot '<NX install root>'. A successful compile only proves the members
//   and overloads resolved; it does not prove the model runs correctly.

using System;
using System.Collections.Generic;

using NXOpen;
using NXOpen.UF;

// The class name is deliberately fixed, so the renderer only has to substitute
// the two placeholders in this file.
public class Nx12Journal
{
    // ------------------------------------------------------- configuration
    //
    // Single configuration entry point. A renderer substitutes the placeholder
    // once, and every diagnostic, undo mark and log line then uses this value.

    // The renderer substitutes both placeholders in this file.
    public const string JournalName = "{{JOURNAL_NAME}}";

    // --------------------------------------------------------- journal state
    //
    // Set once, at the top of Run(). Log() reads it through this field and
    // tolerates it being null, so a failure that happens before the session
    // exists can still be reported on stderr.

    private static Session _session;

    // -------------------------------------------------------- rollback state
    //
    // What actually happened to the undo mark, recorded by UndoToMark() and
    // read by Main(). The three values are the ones the failure log prints:
    // "not-attempted", "succeeded" and "failed".
    //
    // This is a field rather than a return value because Run() reports failure
    // by rethrowing: a caller cannot receive a status from a method that
    // throws. The field is reset at the top of every run.
    //
    // RollbackState.Succeeded is assigned only after session.UndoToMark() has
    // returned normally. Assigning it before the call, or in the code that
    // decides to attempt a rollback, would report a rollback that never
    // completed.

    private enum RollbackState
    {
        NotAttempted,
        Succeeded,
        Failed
    }

    private static RollbackState _rollbackState = RollbackState.NotAttempted;

    // The exception thrown by a failed rollback, kept apart from the failure
    // that caused it. Never allowed to replace the original exception.
    private static Exception _rollbackException;

    // One line describing the recorded rollback outcome. Never throws, so a
    // diagnostic cannot turn into a second failure.
    private static string RollbackStatus()
    {
        switch (_rollbackState)
        {
            case RollbackState.Succeeded:
                return "succeeded - the part was rolled back to the journal undo mark";
            case RollbackState.Failed:
                return "failed - the rollback did not complete and the part may "
                    + "be left partially modified";
            default:
                return "not-attempted - no undo mark was restored, so the part "
                    + "was NOT rolled back";
        }
    }

    // ------------------------------------------------------------ diagnostics

    // Report a diagnostic without ever throwing.
    private static void Log(string message)
    {
        string text = (message == null) ? string.Empty : message;

        try
        {
            Console.Error.WriteLine(text);
        }
        catch (Exception)
        {
            // Some NX hosts run the journal without an attached console, and
            // writing to a missing stderr can fail. The Listing Window copy
            // below is the fallback, so losing this copy is not fatal.
        }

        Session session = _session;
        if (session == null)
        {
            return;
        }

        try
        {
            // NX12-API: NXOpen.Session.ListingWindow | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
            ListingWindow window = session.ListingWindow;
            // NX12-API: NXOpen.ListingWindow.Open | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
            window.Open();
            // NX12-API: NXOpen.ListingWindow.WriteLine | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
            window.WriteLine(text);
        }
        catch (Exception)
        {
            // The Listing Window is optional; the stderr line above already
            // carried the message, so losing this copy is not fatal.
        }
    }

    // ------------------------------------------------------- cleanup helpers

    // Record a builder the moment it exists, so cleanup cannot miss it.
    private static Builder RegisterBuilder(List<Builder> builders, Builder builder)
    {
        builders.Add(builder);
        return builder;
    }

    // Release every builder this journal owns, newest first. Never throws.
    private static void DestroyBuilders(List<Builder> builders)
    {
        while (builders.Count > 0)
        {
            int last = builders.Count - 1;
            Builder builder = builders[last];
            builders.RemoveAt(last);
            if (builder == null)
            {
                continue;
            }

            try
            {
                // NX12-API: NXOpen.Builder.Destroy | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
                builder.Destroy();
            }
            catch (Exception ex)
            {
                // One failed Destroy() must not skip the remaining builders,
                // and must not stop the caller from restoring the undo mark.
                Log(string.Concat(
                    "A builder could not be destroyed cleanly: ",
                    Environment.NewLine,
                    ex.ToString()));
            }
        }
    }

    // Restore the undo mark. Never throws, so it cannot mask the real error.
    // Records what really happened, so Main() never has to guess.
    private static void UndoToMark(Session session, Session.UndoMarkId undoMark)
    {
        try
        {
            // NX12-API: NXOpen.Session.UndoToMark | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
            session.UndoToMark(undoMark, JournalName);

            // Reached only if the call above returned normally.
            _rollbackState = RollbackState.Succeeded;
        }
        catch (Exception ex)
        {
            // The rollback failed. Record that, and keep the rollback exception
            // where Main() can report it without it replacing the original.
            _rollbackState = RollbackState.Failed;
            _rollbackException = ex;

            Log(string.Concat(
                "Rollback to the journal undo mark failed: ",
                Environment.NewLine,
                ex.ToString()));
        }
    }

    // ------------------------------------------------------------ modeling body

    // Do the journal's actual work. Throw on failure; return normally on
    // success.
    //
    // UNVERIFIED: this body is a placeholder. Replace it with one small,
    // version-verified operation before running the journal against a part.
    private static void RunModeling(Session session, Part workPart, List<Builder> builders)
    {
        // Put an evidence comment beside each nontrivial call. The comment
        // begins with the evidence marker, then the member path, then the
        // fields that references/api-validation.md defines, separated by "|":
        //
        //     <marker> <NXOpen.Member.Path> | source=<source> | file=<index>
        //              | version=<x.y.z> | binding=<dotnet|python>
        //
        // A C# call verified against this installation would carry its member
        // path along with source=local-xml,
        // file=NXBIN/managed/NXOpen.xml, version=12.0.0.27 and binding=dotnet.
        //
        // Keep each evidence comment on ONE line. A multi-line comment is read
        // as several separate, incomplete entries.
        //
        // The literal marker is spelled out in references/api-validation.md. It
        // is left out here so that an unfilled scaffold does not carry a
        // comment that looks like real evidence.
        //
        // Register a builder as soon as it is created, so that a failure between
        // creation and the end of this method cannot leak it:
        //
        //   Builder builder = RegisterBuilder(builders, ... CreateXxxBuilder(...));
        //
        // Never rely on a recorded object handle, a selection index or a
        // machine-specific path. Resolve objects by stable names, attributes or
        // geometric intent instead.
        //
        // session, workPart and builders are unused while this is a scaffold.
        Log(JournalName + ": scaffold only; no modeling operation is configured.");
    }

    // -------------------------------------------------------------- execution

    // Run the journal. Throws the ORIGINAL exception on failure, after
    // builders are destroyed and a rollback has been attempted. Whether that
    // attempt happened, and whether it worked, is recorded in _rollbackState
    // rather than assumed.
    private static void Run()
    {
        // Every run starts from "nothing has been rolled back yet". A journal
        // that fails before the undo mark exists must not inherit a status from
        // an earlier run or from a stale field.
        _rollbackState = RollbackState.NotAttempted;
        _rollbackException = null;

        // NX12-API: NXOpen.Session.GetSession | source=nx12-example | file=UGOPEN/SampleNXOpenApplications/.NET/NXOpenExamples/EX_Curve_CreateArc.cs | binding=dotnet | version=12.0.0.27 | status=inferred
        // GetSession exists in the shipped assembly and in Siemens' own NX 12
        // sample, but it has no entry in NXOpen.xml, so the local index cannot
        // confirm it. The evidence is the sample, not the index.
        Session session = Session.GetSession();
        _session = session;

        // NX12-API: NXOpen.Session.Parts | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
        // NX12-API: NXOpen.PartCollection.Work | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
        Part workPart = session.Parts.Work;
        if (workPart == null)
        {
            // Fail before any mutation, so there is nothing to roll back.
            throw new InvalidOperationException(
                "Open a disposable NX 12 work part before running this journal.");
        }

        List<Builder> builders = new List<Builder>();
        bool rollbackNeeded = false;

        // NX12-API: NXOpen.Session.MarkVisibility.Visible | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
        // NX12-API: NXOpen.Session.SetUndoMark | source=local-xml | file=NXBIN/managed/NXOpen.xml | binding=dotnet | version=12.0.0.27 | status=verified-local
        // A visible mark is created before the first mutation, so an operator
        // can also undo the whole journal by hand.
        Session.UndoMarkId undoMark = session.SetUndoMark(
            Session.MarkVisibility.Visible,
            JournalName);

        try
        {
            RunModeling(session, workPart, builders);
        }
        catch (Exception)
        {
            // Bare "throw;" inside catch rethrows the ORIGINAL exception and
            // keeps its stack trace. Nothing is logged here: the finally block
            // below runs first, and Main reports the exception once, in full,
            // after cleanup and rollback have already finished.
            rollbackNeeded = true;
            throw;
        }
        finally
        {
            // Ordering is load-bearing. DestroyBuilders() runs first and cannot
            // throw, so (a) one failed Destroy() cannot skip the remaining
            // builders, (b) a failed cleanup cannot prevent the rollback that
            // follows, and (c) the rethrown exception above is never replaced.
            //
            // The undo mark is restored only when this journal actually failed.
            // Every builder here was created after the mark, so rolling back
            // first could invalidate the very objects cleanup still has to
            // release.
            DestroyBuilders(builders);
            if (rollbackNeeded)
            {
                UndoToMark(session, undoMark);
            }
        }

        // No save, Save As, close, delete, export or submit happens here on
        // purpose. Add those only when the user has explicitly asked for the
        // operation and the destination.
    }

    // ------------------------------------------------------------- entry point

    // Journal entry point.
    //
    // Returns 0 on success and the documented nonzero code 1 on failure, so a
    // caller can identify the outcome from the return value alone. The
    // exception object that Run() rethrows is the original one, is reported in
    // full here, and is never replaced by a cleanup, rollback or logging
    // failure.
    //
    // The rollback sentence is built from the recorded state, not from an
    // assumption: a journal that failed before the undo mark existed says so,
    // and a failed rollback is reported as failed.
    public static int Main(string[] args)
    {
        try
        {
            Run();
            return 0;
        }
        catch (Exception ex)
        {
            // The original exception is reported first, in full and unchanged.
            Log(string.Concat(
                JournalName,
                ": journal failed. Rollback: ",
                RollbackStatus(),
                ".",
                Environment.NewLine,
                ex.ToString()));

            if (_rollbackException != null)
            {
                // Reported separately and clearly labelled. It did not replace
                // the exception above and is not the cause of the failure.
                Log(string.Concat(
                    JournalName,
                    ": the rollback attempt itself failed:",
                    Environment.NewLine,
                    _rollbackException.ToString()));
            }

            return 1;
        }
    }

    // Unload option, as used by Siemens' own NX 12 C# sample.
    //
    // NX12-API: NXOpen.UF.UFConstants.UF_UNLOAD_IMMEDIATELY | source=nx12-example | file=UGOPEN/SampleNXOpenApplications/.NET/NXOpenExamples/EX_Curve_CreateArc.cs | binding=dotnet | version=12.0.0.27 | status=inferred
    // The NXOpen.UF.xml documentation file names the UFConstants type but
    // documents none of its fields, so the index cannot confirm this constant.
    // The evidence is Siemens' shipped sample, which returns exactly this value
    // from exactly this method signature.
    public static int GetUnloadOption(string dummy)
    {
        return UFConstants.UF_UNLOAD_IMMEDIATELY;
    }
}
