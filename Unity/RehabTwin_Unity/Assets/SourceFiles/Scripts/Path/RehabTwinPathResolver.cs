using System;
using System.IO;
using UnityEngine;

public static class RehabTwinPathResolver
{
    // ---------------------------------------------------------------------
    // Unity Project
    // ---------------------------------------------------------------------

    public static string GetUnityProjectRoot()
    {
        DirectoryInfo assetsDirectory =
            new DirectoryInfo(
                Application.dataPath
            );

        if (assetsDirectory.Parent == null)
        {
            throw new InvalidOperationException(
                "Could not determine Unity project root."
            );
        }

        return assetsDirectory.Parent.FullName;
    }

    // ---------------------------------------------------------------------
    // Common Parent
    // ---------------------------------------------------------------------

    public static string GetCommonParent()
    {
        DirectoryInfo unityProjectDirectory =
            new DirectoryInfo(
                GetUnityProjectRoot()
            );

        if (unityProjectDirectory.Parent == null)
        {
            throw new InvalidOperationException(
                "Could not determine common RehabTwin parent."
            );
        }

        return unityProjectDirectory.Parent.FullName;
    }

    // ---------------------------------------------------------------------
    // Python RehabTwin Root
    // ---------------------------------------------------------------------

    public static string GetPythonRoot()
    {
        string commonParent =
            GetCommonParent();

        string pythonRoot =
            Path.Combine(
                commonParent,
                "RehabTwin(V4)"
            );

        return Path.GetFullPath(
            pythonRoot
        );
    }

    // ---------------------------------------------------------------------
    // Data Root
    // ---------------------------------------------------------------------

    public static string GetDataRoot()
    {
        return Path.Combine(
            GetPythonRoot(),
            "data"
        );
    }

    // ---------------------------------------------------------------------
    // Patient Root
    // ---------------------------------------------------------------------

    public static string GetPatientRoot(
        string patientId
    )
    {
        if (string.IsNullOrWhiteSpace(
                patientId))
        {
            throw new ArgumentException(
                "Patient ID cannot be empty.",
                nameof(patientId)
            );
        }

        string normalisedPatientId =
            patientId.Trim().ToUpper();

        return Path.Combine(
            GetDataRoot(),
            "patients",
            normalisedPatientId
        );
    }

    // ---------------------------------------------------------------------
    // Patient Profile
    // ---------------------------------------------------------------------

    public static string GetPatientProfilePath(
        string patientId
    )
    {
        return Path.Combine(
            GetPatientRoot(patientId),
            "profile.json"
        );
    }

    // ---------------------------------------------------------------------
    // Patient Sessions
    // ---------------------------------------------------------------------

    public static string GetPatientSessionsRoot(
        string patientId
    )
    {
        return Path.Combine(
            GetPatientRoot(patientId),
            "sessions"
        );
    }

    // ---------------------------------------------------------------------
    // Patient Existence
    // ---------------------------------------------------------------------

    public static bool PatientExists(
        string patientId
    )
    {
        if (string.IsNullOrWhiteSpace(patientId))
        {
            return false;
        }

        string patientRoot;

        try
        {
            patientRoot =
                GetPatientRoot(patientId);
        }
        catch
        {
            return false;
        }

        if (!Directory.Exists(patientRoot))
        {
            return false;
        }

        return File.Exists(
            GetPatientProfilePath(patientId)
        );
    }

    // ---------------------------------------------------------------------
    // Patient Session Existence
    // ---------------------------------------------------------------------

    public static bool PatientHasSessions(
        string patientId
    )
    {
        if (!PatientExists(patientId))
        {
            return false;
        }

        string sessionsRoot =
            GetPatientSessionsRoot(
                patientId
            );

        if (!Directory.Exists(
                sessionsRoot))
        {
            return false;
        }

        string[] sessionFiles =
            Directory.GetFiles(
                sessionsRoot,
                "Session_*.json"
            );

        return
            sessionFiles != null &&
            sessionFiles.Length > 0;
    }

    // ---------------------------------------------------------------------
    // Validation
    // ---------------------------------------------------------------------

    public static bool ValidateStructure(
        out string error
    )
    {
        error = "";

        string pythonRoot;

        try
        {
            pythonRoot =
                GetPythonRoot();
        }
        catch (Exception exception)
        {
            error =
                exception.Message;

            return false;
        }

        if (!Directory.Exists(
                pythonRoot))
        {
            error =
                "RehabTwin Python root was not found:\n" +
                pythonRoot;

            return false;
        }

        string dataRoot =
            GetDataRoot();

        if (!Directory.Exists(
                dataRoot))
        {
            error =
                "RehabTwin data directory was not found:\n" +
                dataRoot;

            return false;
        }

        return true;
    }
}