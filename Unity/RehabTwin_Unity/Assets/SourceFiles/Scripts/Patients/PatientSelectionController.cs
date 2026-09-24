using System;
using System.Collections.Generic;
using UnityEngine;

public class PatientSelectionController : MonoBehaviour
{
    // ---------------------------------------------------------------------
    // References
    // ---------------------------------------------------------------------

    [Header("References")]
    public RehabTwinSessionController sessionController;

    // ---------------------------------------------------------------------
    // Developer Controls
    // ---------------------------------------------------------------------

    [Header("Developer Controls")]
    public bool showSelector = true;

    // ---------------------------------------------------------------------
    // Runtime
    // ---------------------------------------------------------------------

    private PatientDirectory patientDirectory;

    private List<string> patientIds =
        new List<string>();

    private Vector2 scrollPosition;

    private string newPatientId = "";

    private string newPatientName = "";

    private string creationMessage = "";

    // ---------------------------------------------------------------------
    // Unity
    // ---------------------------------------------------------------------

    private void Awake()
    {
        patientDirectory =
            new PatientDirectory();

        RefreshPatients();

        if (sessionController == null)
        {
            sessionController =
                FindAnyObjectByType<
                    RehabTwinSessionController
                >();
        }
    }

    // ---------------------------------------------------------------------
    // PATIENT LIST
    // ---------------------------------------------------------------------

    public void RefreshPatients()
    {
        if (patientDirectory == null)
        {
            patientDirectory =
                new PatientDirectory();
        }

        patientIds =
            patientDirectory.GetPatientIds();
    }

    public List<string> GetPatientIds()
    {
        RefreshPatients();

        return new List<string>(
            patientIds
        );
    }

    // ---------------------------------------------------------------------
    // SELECT PATIENT
    // ---------------------------------------------------------------------

    public bool SelectPatient(
        string selectedPatientId
    )
    {
        if (sessionController == null)
        {
            sessionController =
                FindAnyObjectByType<
                    RehabTwinSessionController
                >();
        }

        if (sessionController == null)
        {
            Debug.LogError(
                "[PatientSelector] " +
                "RehabTwinSessionController not found."
            );

            return false;
        }

        bool selected =
            sessionController.SetPatient(
                selectedPatientId
            );

        if (selected)
        {
            creationMessage = "";

            Debug.Log(
                "[PatientSelector] " +
                "Selected patient: " +
                selectedPatientId
            );
        }

        return selected;
    }

    // ---------------------------------------------------------------------
    // CURRENT PATIENT
    // ---------------------------------------------------------------------

    public string GetSelectedPatient()
    {
        if (sessionController == null)
        {
            sessionController =
                FindAnyObjectByType<
                    RehabTwinSessionController
                >();
        }

        if (sessionController == null)
        {
            return "";
        }

        return sessionController.GetCurrentPatientId();
    }

    // ---------------------------------------------------------------------
    // CREATE PATIENT
    // ---------------------------------------------------------------------

    public bool CreatePatient()
    {
        if (sessionController == null)
        {
            sessionController =
                FindAnyObjectByType<
                    RehabTwinSessionController
                >();
        }

        if (sessionController == null)
        {
            creationMessage =
                "Session Controller not found.";

            return false;
        }

        if (sessionController.IsSessionActive())
        {
            creationMessage =
                "End the active session first.";

            return false;
        }

        if (patientDirectory == null)
        {
            patientDirectory =
                new PatientDirectory();
        }

        if (string.IsNullOrWhiteSpace(newPatientId))
        {
            creationMessage =
                "Enter a Patient ID.";

            return false;
        }

        if (string.IsNullOrWhiteSpace(newPatientName))
        {
            creationMessage =
                "Enter a patient name.";

            return false;
        }

        bool created =
            patientDirectory.CreatePatient(
                newPatientId,
                newPatientName
            );

        if (!created)
        {
            creationMessage =
                "Patient could not be created.";

            return false;
        }

        string createdPatientId =
            newPatientId.Trim().ToUpper();

        RefreshPatients();

        // Automatically select the newly-created patient.
        bool selected =
            SelectPatient(
                createdPatientId
            );

        if (selected)
        {
            creationMessage =
                "Created and selected " +
                createdPatientId;
        }
        else
        {
            creationMessage =
                "Patient created: " +
                createdPatientId;
        }

        newPatientId = "";
        newPatientName = "";

        return true;
    }

    // ---------------------------------------------------------------------
    // DEVELOPER GUI
    // ---------------------------------------------------------------------

    private void OnGUI()
    {
        if (!showSelector)
        {
            return;
        }

        if (sessionController == null)
        {
            sessionController =
                FindAnyObjectByType<
                    RehabTwinSessionController
                >();
        }

        const float panelWidth = 350f;
        const float panelHeight = 500f;

        Rect panelRect =
            new Rect(
                Screen.width -
                panelWidth -
                10f,
                10f,
                panelWidth,
                panelHeight
            );

        GUI.Box(
            panelRect,
            "RehabTwin Patient Manager"
        );

        GUILayout.BeginArea(
            new Rect(
                panelRect.x + 10f,
                panelRect.y + 25f,
                panelRect.width - 20f,
                panelRect.height - 35f
            )
        );

        // -------------------------------------------------------------
        // CURRENT PATIENT
        // -------------------------------------------------------------

        GUILayout.Label(
            "Selected: " +
            GetSelectedPatient()
        );

        GUILayout.Space(5f);

        // -------------------------------------------------------------
        // ADD PATIENT
        // -------------------------------------------------------------

        GUILayout.Label(
            "Add Patient"
        );

        GUILayout.Label(
            "Patient ID"
        );

        newPatientId =
            GUILayout.TextField(
                newPatientId,
                GUILayout.Height(24f)
            );

        GUILayout.Label(
            "Name"
        );

        newPatientName =
            GUILayout.TextField(
                newPatientName,
                GUILayout.Height(24f)
            );

        GUILayout.Space(5f);

        if (GUILayout.Button(
                "CREATE PATIENT",
                GUILayout.Height(28f)))
        {
            CreatePatient();
        }

        if (!string.IsNullOrEmpty(
                creationMessage))
        {
            GUILayout.Space(4f);

            GUILayout.Label(
                creationMessage
            );
        }

        GUILayout.Space(10f);

        // -------------------------------------------------------------
        // REFRESH
        // -------------------------------------------------------------

        if (GUILayout.Button(
                "REFRESH PATIENTS",
                GUILayout.Height(25f)))
        {
            RefreshPatients();
        }

        GUILayout.Space(6f);

        // -------------------------------------------------------------
        // PATIENT LIST
        // -------------------------------------------------------------

        GUILayout.Label(
            "Patients"
        );

        scrollPosition =
            GUILayout.BeginScrollView(
                scrollPosition,
                GUILayout.Height(220f)
            );

        if (patientIds.Count == 0)
        {
            GUILayout.Label(
                "No patients found."
            );
        }
        else
        {
            foreach (string id in patientIds)
            {
                bool isSelected =
                    string.Equals(
                        id,
                        GetSelectedPatient(),
                        StringComparison.OrdinalIgnoreCase
                    );

                GUI.enabled =
                    !isSelected;

                string buttonText =
                    isSelected
                        ? id + "  [SELECTED]"
                        : id;

                if (GUILayout.Button(
                        buttonText,
                        GUILayout.Height(30f)))
                {
                    SelectPatient(id);
                }
            }

            GUI.enabled = true;
        }

        GUILayout.EndScrollView();

        GUILayout.EndArea();
    }
}