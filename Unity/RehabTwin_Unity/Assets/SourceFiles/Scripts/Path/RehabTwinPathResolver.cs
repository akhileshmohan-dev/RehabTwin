using System;
using System.IO;
using UnityEngine;

public static class RehabTwinPathResolver
{
    // ---------------------------------------------------------------------
    // Unity Project / Runtime Root
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

    public static string GetRuntimeRoot()
    {
        // In a built Unity application:
        //
        // Runtime/
        // ├── RehabTwin.exe
        // └── RehabTwin_Data/
        //
        // Application.dataPath points to RehabTwin_Data.
        //
        // In the Unity Editor, Application.dataPath points to:
        // Unity/RehabTwin_Unity/Assets
        //
        // We resolve the actual RehabTwin Python/backend root
        // by searching upward for the expected project structure.

        string unityProjectRoot =
            GetUnityProjectRoot();

        string developmentRoot =
            FindDevelopmentRoot(
                unityProjectRoot
            );

        if (!string.IsNullOrEmpty(
                developmentRoot))
        {
            return developmentRoot;
        }

        // For a future standalone build, the runtime root
        // is the directory containing the executable.
        DirectoryInfo dataDirectory =
            new DirectoryInfo(
                Application.dataPath
            );

        if (dataDirectory.Parent == null)
        {
            throw new InvalidOperationException(
                "Could not determine Unity runtime root."
            );
        }

        return dataDirectory.Parent.FullName;
    }

    // ---------------------------------------------------------------------
    // Development Root Detection
    // ---------------------------------------------------------------------

    private static string FindDevelopmentRoot(
        string startDirectory
    )
    {
        DirectoryInfo current =
            new DirectoryInfo(
                startDirectory
            );

        while (current != null)
        {
            string requirementsPath =
                Path.Combine(
                    current.FullName,
                    "requirements.txt"
                );

            string rehabilitationDirectory =
                Path.Combine(
                    current.FullName,
                    "rehabilitation"
                );

            string exercisesDirectory =
                Path.Combine(
                    current.FullName,
                    "exercises"
                );

            string dataDirectory =
                Path.Combine(
                    current.FullName,
                    "data"
                );

            if (
                File.Exists(requirementsPath) &&
                Directory.Exists(rehabilitationDirectory) &&
                Directory.Exists(exercisesDirectory) &&
                Directory.Exists(dataDirectory)
            )
            {
                return current.FullName;
            }

            current =
                current.Parent;
        }

        return null;
    }

    // ---------------------------------------------------------------------
    // Python / Backend Root
    // ---------------------------------------------------------------------

    public static string GetPythonRoot()
    {
        string runtimeRoot =
            GetRuntimeRoot();

        // Development layout:
        //
        // RehabTwin(V4)/
        // ├── rehabilitation/
        // ├── exercises/
        // ├── data/
        // └── Unity/
        //
        // Deployment layout can later use:
        //
        // Runtime/
        // ├── RehabTwin.exe
        // └── backend/
        //
        string backendDirectory =
            Path.Combine(
                runtimeRoot,
                "backend"
            );

        if (Directory.Exists(
                backendDirectory))
        {
            return Path.GetFullPath(
                backendDirectory
            );
        }

        return Path.GetFullPath(
            runtimeRoot
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
    // Exercise Configuration
    // ---------------------------------------------------------------------

    public static string GetExerciseRoot()
    {
        return Path.Combine(
            GetPythonRoot(),
            "exercises"
        );
    }

    public static string GetExerciseConfigPath()
    {
        return Path.Combine(
            GetExerciseRoot(),
            "exercises.csv"
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
    // Structure Validation
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
                "RehabTwin backend root was not found:\n" +
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