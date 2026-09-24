using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[Serializable]
public class PatientProfile
{
    public string patient_id;
    public string name;
    public string created_at;
    public string updated_at;
}

public class PatientDirectory
{
    // ---------------------------------------------------------------------
    // Patient Discovery
    // ---------------------------------------------------------------------

    public List<string> GetPatientIds()
    {
        List<string> patientIds =
            new List<string>();

        string patientsRoot =
            Path.Combine(
                RehabTwinPathResolver.GetDataRoot(),
                "patients"
            );

        if (!Directory.Exists(patientsRoot))
        {
            return patientIds;
        }

        string[] directories =
            Directory.GetDirectories(
                patientsRoot
            );

        foreach (string directory in directories)
        {
            string patientId =
                Path.GetFileName(
                    directory
                );

            if (string.IsNullOrWhiteSpace(patientId))
            {
                continue;
            }

            string profilePath =
                Path.Combine(
                    directory,
                    "profile.json"
                );

            if (!File.Exists(profilePath))
            {
                continue;
            }

            patientIds.Add(
                patientId.ToUpper()
            );
        }

        patientIds.Sort();

        return patientIds;
    }

    // ---------------------------------------------------------------------
    // Create Patient
    // ---------------------------------------------------------------------

    public bool CreatePatient(
        string patientId,
        string name
    )
    {
        if (string.IsNullOrWhiteSpace(patientId))
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Patient ID cannot be empty."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(name))
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Patient name cannot be empty."
            );

            return false;
        }

        string normalisedPatientId =
            patientId.Trim().ToUpper();

        string trimmedName =
            name.Trim();

        // -------------------------------------------------------------
        // Basic ID validation
        // -------------------------------------------------------------

        foreach (char character in normalisedPatientId)
        {
            if (
                !char.IsLetterOrDigit(character) &&
                character != '_' &&
                character != '-'
            )
            {
                Debug.LogError(
                    "[PatientDirectory] " +
                    "Patient ID contains invalid characters."
                );

                return false;
            }
        }

        // -------------------------------------------------------------
        // Check if patient already exists
        // -------------------------------------------------------------

        if (
            RehabTwinPathResolver.PatientExists(
                normalisedPatientId
            )
        )
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Patient already exists: " +
                normalisedPatientId
            );

            return false;
        }

        // -------------------------------------------------------------
        // Resolve patient directory
        // -------------------------------------------------------------

        string patientRoot;

        try
        {
            patientRoot =
                RehabTwinPathResolver.GetPatientRoot(
                    normalisedPatientId
                );
        }
        catch (Exception exception)
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Could not resolve patient directory:\n" +
                exception.Message
            );

            return false;
        }

        string sessionsRoot =
            RehabTwinPathResolver.GetPatientSessionsRoot(
                normalisedPatientId
            );

        // -------------------------------------------------------------
        // Create directories
        // -------------------------------------------------------------

        try
        {
            Directory.CreateDirectory(
                patientRoot
            );

            Directory.CreateDirectory(
                sessionsRoot
            );
        }
        catch (Exception exception)
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Failed to create patient directories:\n" +
                exception.Message
            );

            return false;
        }

        // -------------------------------------------------------------
        // Create profile
        // -------------------------------------------------------------

        string timestamp =
            DateTime.UtcNow.ToString(
                "O"
            );

        PatientProfile profile =
            new PatientProfile();

        profile.patient_id =
            normalisedPatientId;

        profile.name =
            trimmedName;

        profile.created_at =
            timestamp;

        profile.updated_at =
            timestamp;

        string profilePath =
            RehabTwinPathResolver.GetPatientProfilePath(
                normalisedPatientId
            );

        try
        {
            string json =
                JsonUtility.ToJson(
                    profile,
                    true
                );

            File.WriteAllText(
                profilePath,
                json
            );
        }
        catch (Exception exception)
        {
            Debug.LogError(
                "[PatientDirectory] " +
                "Failed to write patient profile:\n" +
                exception.Message
            );

            return false;
        }

        Debug.Log(
            "[PatientDirectory] " +
            "Patient created: " +
            normalisedPatientId
        );

        Debug.Log(
            "[PatientDirectory] " +
            "Profile: " +
            profilePath
        );

        return true;
    }

    // ---------------------------------------------------------------------
    // Patient Check
    // ---------------------------------------------------------------------

    public bool Exists(
        string patientId
    )
    {
        return RehabTwinPathResolver.PatientExists(
            patientId
        );
    }

    // ---------------------------------------------------------------------
    // Sessions
    // ---------------------------------------------------------------------

    public bool HasSessions(
        string patientId
    )
    {
        return RehabTwinPathResolver.PatientHasSessions(
            patientId
        );
    }

    public int GetSessionCount(
        string patientId
    )
    {
        if (!Exists(patientId))
        {
            return 0;
        }

        string sessionsRoot =
            RehabTwinPathResolver.GetPatientSessionsRoot(
                patientId
            );

        if (!Directory.Exists(sessionsRoot))
        {
            return 0;
        }

        string[] sessionFiles =
            Directory.GetFiles(
                sessionsRoot,
                "Session_*.json"
            );

        return sessionFiles.Length;
    }
}