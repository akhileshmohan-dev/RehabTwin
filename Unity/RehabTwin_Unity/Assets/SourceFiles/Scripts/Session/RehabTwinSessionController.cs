using System.IO;
using UnityEngine;
using DiagnosticsProcess = System.Diagnostics.Process;
using DiagnosticsProcessStartInfo = System.Diagnostics.ProcessStartInfo;

public class RehabTwinSessionController : MonoBehaviour
{
    // ---------------------------------------------------------------------
    // Session Types
    // ---------------------------------------------------------------------

    public enum SessionMode
    {
        None,
        Live,
        Replay
    }

    public enum SessionState
    {
        Idle,
        Starting,
        Running,
        Ending
    }

    // ---------------------------------------------------------------------
    // Python Configuration
    // ---------------------------------------------------------------------

    [Header("Python / Live Analysis")]
    [Tooltip(
        "Automatically resolve the Python project from the shared " +
        "RehabTwin parent folder."
    )]
    public bool autoResolvePythonPaths = true;

    [Tooltip(
        "Relative path to the Python executable inside the RehabTwin " +
        "Python project."
    )]
    public string pythonExecutableRelativePath =
        @".venv\Scripts\python.exe";

    [Tooltip(
        "Resolved Python executable. " +
        "Automatically filled when autoResolvePythonPaths is enabled."
    )]
    public string pythonExecutable = "";

    [Tooltip(
        "Resolved RehabTwin Python project root."
    )]
    public string pythonWorkingDirectory = "";

    [Tooltip("Python module used for live webcam analysis.")]
    public string liveAnalysisCommand =
        "-m rehabilitation.live_analysis";

    [Header("Launch Settings")]
    public bool launchPythonForLive = true;

    public bool unityEditorDevelopmentMode = true;

    // ---------------------------------------------------------------------
    // Patient
    // ---------------------------------------------------------------------

    [Header("Current Patient")]
    [Tooltip(
        "Patient selected for the next Live or Replay session."
    )]
    public string patientId = "PATIENT_001";

    // ---------------------------------------------------------------------
    // Module References
    // ---------------------------------------------------------------------

    [Header("Module References")]
    public PoseSessionRecorder poseSessionRecorder;

    public PoseSessionReplay poseSessionReplay;

    public AvatarTrackingController avatarTrackingController;

    // ---------------------------------------------------------------------
    // Developer Controls
    // ---------------------------------------------------------------------

    [Header("Developer Controls")]
    public bool showDeveloperControls = true;

    // ---------------------------------------------------------------------
    // Runtime State
    // ---------------------------------------------------------------------

    private SessionMode currentMode = SessionMode.None;

    private SessionState currentState =
        SessionState.Idle;

    private DiagnosticsProcess pythonProcess;

    private bool replayStarted = false;

    // ---------------------------------------------------------------------
    // Unity
    // ---------------------------------------------------------------------

    private void Start()
    {
        currentMode =
            SessionMode.None;

        currentState =
            SessionState.Idle;

        ResolveReferences();

        ResolvePythonPaths();

        ApplyPatientToModules();

        // Recorder is controlled only by this Session Controller.
        if (poseSessionRecorder != null)
        {
            poseSessionRecorder.enabled = false;
        }

        Debug.Log(
            "[SessionController] Ready."
        );

        Debug.Log(
            "[SessionController] Current patient: " +
            patientId
        );

        Debug.Log(
            "[SessionController] Python root: " +
            pythonWorkingDirectory
        );

        Debug.Log(
            "[SessionController] Python executable: " +
            pythonExecutable
        );
    }

    private void Update()
    {
        CheckReplayCompletion();
    }

    private void OnApplicationQuit()
    {
        StopLiveAnalysis();
        StopSessionRecording();
        StopReplay();

        if (avatarTrackingController != null)
        {
            avatarTrackingController.ResetAvatarToRestPose();
            avatarTrackingController.enabled = false;
        }
        else
        {
            AvatarTrackingController avatar =
                FindAnyObjectByType<AvatarTrackingController>();

            if (avatar != null)
            {
                avatar.ResetAvatarToRestPose();
                avatar.enabled = false;
            }
        }
    }

    // ---------------------------------------------------------------------
    // REFERENCE RESOLUTION
    // ---------------------------------------------------------------------

    private void ResolveReferences()
    {
        if (avatarTrackingController == null)
        {
            avatarTrackingController =
                FindAnyObjectByType<AvatarTrackingController>();
        }

        if (poseSessionRecorder == null)
        {
            poseSessionRecorder =
                FindAnyObjectByType<PoseSessionRecorder>();
        }

        if (poseSessionReplay == null)
        {
            poseSessionReplay =
                FindAnyObjectByType<PoseSessionReplay>();
        }

        // Automatically connect PoseReceiver to Recorder.
        if (
            poseSessionRecorder != null &&
            poseSessionRecorder.poseReceiver == null
        )
        {
            PoseReceiver poseReceiver =
                FindAnyObjectByType<PoseReceiver>();

            if (poseReceiver != null)
            {
                poseSessionRecorder.poseReceiver =
                    poseReceiver;

                Debug.Log(
                    "[SessionController] " +
                    "PoseReceiver automatically assigned " +
                    "to PoseSessionRecorder."
                );
            }
        }

        // Automatically connect PoseReceiver to Replay.
        if (
            poseSessionReplay != null &&
            poseSessionReplay.poseReceiver == null
        )
        {
            PoseReceiver poseReceiver =
                FindAnyObjectByType<PoseReceiver>();

            if (poseReceiver != null)
            {
                poseSessionReplay.poseReceiver =
                    poseReceiver;

                Debug.Log(
                    "[SessionController] " +
                    "PoseReceiver automatically assigned " +
                    "to PoseSessionReplay."
                );
            }
        }

        if (avatarTrackingController == null)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "AvatarTrackingController not found."
            );
        }

        if (poseSessionRecorder == null)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "PoseSessionRecorder not found."
            );
        }

        if (poseSessionReplay == null)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "PoseSessionReplay not found."
            );
        }
    }

    // ---------------------------------------------------------------------
    // PYTHON PATH RESOLUTION
    // ---------------------------------------------------------------------

    private void ResolvePythonPaths()
    {
        if (!autoResolvePythonPaths)
        {
            return;
        }

        try
        {
            string pythonRoot =
                RehabTwinPathResolver.GetPythonRoot();

            string executablePath =
                Path.Combine(
                    pythonRoot,
                    pythonExecutableRelativePath
                );

            pythonWorkingDirectory =
                Path.GetFullPath(
                    pythonRoot
                );

            pythonExecutable =
                Path.GetFullPath(
                    executablePath
                );

            Debug.Log(
                "[SessionController] " +
                "Python paths resolved automatically."
            );
        }
        catch (System.Exception exception)
        {
            Debug.LogError(
                "[SessionController] " +
                "Failed to resolve Python paths:\n" +
                exception.Message
            );
        }
    }

    // ---------------------------------------------------------------------
    // PATIENT API
    // ---------------------------------------------------------------------

    public bool SetPatient(
        string newPatientId
    )
    {
        if (currentState != SessionState.Idle)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "Cannot change patient while a session is active."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(newPatientId))
        {
            Debug.LogError(
                "[SessionController] " +
                "Patient ID cannot be empty."
            );

            return false;
        }

        string normalisedPatientId =
            newPatientId.Trim().ToUpper();

        // -------------------------------------------------------------
        // Verify that the patient actually exists.
        // -------------------------------------------------------------

        if (!RehabTwinPathResolver.PatientExists(
                normalisedPatientId))
        {
            Debug.LogError(
                "[SessionController] " +
                "Patient does not exist: " +
                normalisedPatientId
            );

            return false;
        }

        patientId =
            normalisedPatientId;

        ResolveReferences();

        if (!ApplyPatientToModules())
        {
            Debug.LogError(
                "[SessionController] " +
                "Failed to apply patient to modules."
            );

            return false;
        }

        Debug.Log(
            "[SessionController] " +
            "Current patient set to: " +
            patientId
        );

        return true;
    }

    public string GetCurrentPatientId()
    {
        return patientId;
    }

    public bool HasPatientSelected()
    {
        return
            !string.IsNullOrWhiteSpace(
                patientId
            ) &&
            RehabTwinPathResolver.PatientExists(
                patientId
            );
    }

    private bool ApplyPatientToModules()
    {
        if (string.IsNullOrWhiteSpace(patientId))
        {
            return false;
        }

        bool recorderOkay = true;

        bool replayOkay = true;

        if (poseSessionRecorder != null)
        {
            recorderOkay =
                poseSessionRecorder.SetPatient(
                    patientId
                );
        }

        if (poseSessionReplay != null)
        {
            replayOkay =
                poseSessionReplay.SetPatient(
                    patientId
                );
        }

        return
            recorderOkay &&
            replayOkay;
    }

    // ---------------------------------------------------------------------
    // LIVE SESSION
    // ---------------------------------------------------------------------

    public void StartLiveSession()
    {
        if (currentState != SessionState.Idle)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "Cannot start Live session. " +
                "Another session is already active."
            );

            return;
        }

        ResolveReferences();

        ResolvePythonPaths();

        if (!HasPatientSelected())
        {
            Debug.LogError(
                "[SessionController] " +
                "Cannot start Live session. " +
                "No valid patient is selected."
            );

            return;
        }

        ApplyPatientToModules();

        Debug.Log(
            "[SessionController] " +
            "Starting Live session."
        );

        currentMode =
            SessionMode.Live;

        currentState =
            SessionState.Starting;

        // Replay must not be active during Live.
        StopReplay();

        // Recorder is enabled only during Live.
        if (poseSessionRecorder != null)
        {
            poseSessionRecorder.enabled = false;
        }

        // Enable avatar tracking.
        if (avatarTrackingController != null)
        {
            avatarTrackingController.enabled = true;
        }

        // Start Python live analysis.
        if (launchPythonForLive)
        {
            bool pythonStarted =
                StartLiveAnalysis();

            if (!pythonStarted)
            {
                Debug.LogError(
                    "[SessionController] " +
                    "Live session could not start because " +
                    "Python failed to launch."
                );

                StopSessionRecording();

                if (avatarTrackingController != null)
                {
                    avatarTrackingController.ResetAvatarToRestPose();
                    avatarTrackingController.enabled = false;
                }

                currentMode =
                    SessionMode.None;

                currentState =
                    SessionState.Idle;

                return;
            }
        }

        // Start recording after Python has started.
        if (!StartSessionRecording())
        {
            Debug.LogError(
                "[SessionController] " +
                "Live session could not start because " +
                "recording failed to start."
            );

            StopLiveAnalysis();

            if (avatarTrackingController != null)
            {
                avatarTrackingController.ResetAvatarToRestPose();
                avatarTrackingController.enabled = false;
            }

            currentMode =
                SessionMode.None;

            currentState =
                SessionState.Idle;

            return;
        }

        currentState =
            SessionState.Running;

        Debug.Log(
            "[SessionController] " +
            "Live session is now RUNNING."
        );

        Debug.Log(
            "[SessionController] " +
            "Patient: " +
            patientId
        );
    }

    // ---------------------------------------------------------------------
    // REPLAY SESSION
    // ---------------------------------------------------------------------

    public void StartReplaySession()
    {
        if (currentState != SessionState.Idle)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "Cannot start Replay session. " +
                "Another session is already active."
            );

            return;
        }

        ResolveReferences();

        if (!HasPatientSelected())
        {
            Debug.LogError(
                "[SessionController] " +
                "Cannot start Replay session. " +
                "No valid patient is selected."
            );

            return;
        }

        if (poseSessionReplay == null)
        {
            Debug.LogError(
                "[SessionController] " +
                "Cannot start Replay. " +
                "PoseSessionReplay was not found."
            );

            return;
        }

        ApplyPatientToModules();

        Debug.Log(
            "[SessionController] " +
            "Starting Replay session."
        );

        currentMode =
            SessionMode.Replay;

        currentState =
            SessionState.Starting;

        // Replay must never record.
        StopSessionRecording();

        // Live Python must not be running.
        StopLiveAnalysis();

        // Enable avatar.
        if (avatarTrackingController != null)
        {
            avatarTrackingController.enabled = true;
        }

        // Make sure replay is stopped before loading.
        poseSessionReplay.PauseReplay();

        // Load newest recorded session for selected patient.
        poseSessionReplay.LoadLatestSession();

        if (!poseSessionReplay.HasSessionLoaded())
        {
            Debug.LogError(
                "[SessionController] " +
                "Replay could not start because " +
                "no valid recorded session was loaded " +
                "for patient " +
                patientId +
                "."
            );

            if (avatarTrackingController != null)
            {
                avatarTrackingController.ResetAvatarToRestPose();
                avatarTrackingController.enabled = false;
            }

            currentMode =
                SessionMode.None;

            currentState =
                SessionState.Idle;

            return;
        }

        // Start replay from the loaded session.
        poseSessionReplay.StartReplay();

        replayStarted =
            poseSessionReplay.IsPlaying();

        if (!replayStarted)
        {
            Debug.LogError(
                "[SessionController] " +
                "Replay failed to enter playing state."
            );

            if (avatarTrackingController != null)
            {
                avatarTrackingController.ResetAvatarToRestPose();
                avatarTrackingController.enabled = false;
            }

            currentMode =
                SessionMode.None;

            currentState =
                SessionState.Idle;

            return;
        }

        currentState =
            SessionState.Running;

        Debug.Log(
            "[SessionController] " +
            "Replay session is now RUNNING."
        );

        Debug.Log(
            "[SessionController] " +
            "Patient: " +
            patientId
        );

        Debug.Log(
            "[SessionController] " +
            "Replay file: " +
            poseSessionReplay.GetLoadedFilePath()
        );

        Debug.Log(
            "[SessionController] " +
            "Replay frames: " +
            poseSessionReplay.GetTotalFrames()
        );
    }

    // ---------------------------------------------------------------------
    // REPLAY COMPLETION
    // ---------------------------------------------------------------------

    private void CheckReplayCompletion()
    {
        if (currentMode != SessionMode.Replay)
        {
            return;
        }

        if (currentState != SessionState.Running)
        {
            return;
        }

        if (!replayStarted)
        {
            return;
        }

        if (poseSessionReplay == null)
        {
            return;
        }

        if (poseSessionReplay.IsPlaying())
        {
            return;
        }

        // Paused manually.
        if (
            poseSessionReplay.GetCurrentFrame() <
            poseSessionReplay.GetTotalFrames()
        )
        {
            return;
        }

        Debug.Log(
            "[SessionController] " +
            "Replay completed."
        );

        EndCurrentSession();
    }

    // ---------------------------------------------------------------------
    // END SESSION
    // ---------------------------------------------------------------------

    public void EndCurrentSession()
    {
        if (currentState == SessionState.Idle)
        {
            Debug.Log(
                "[SessionController] " +
                "No active session."
            );

            return;
        }

        Debug.Log(
            "[SessionController] " +
            "Ending current session."
        );

        currentState =
            SessionState.Ending;

        // Stop Python only for Live sessions.
        if (currentMode == SessionMode.Live)
        {
            StopLiveAnalysis();

            // Save the current Live recording.
            StopSessionRecording();
        }
        else
        {
            // Replay is read-only.
            StopReplay();

            // Ensure recorder is not running.
            StopSessionRecording();
        }

        // Reset avatar and disable tracking.
        if (avatarTrackingController != null)
        {
            avatarTrackingController.ResetAvatarToRestPose();

            avatarTrackingController.enabled = false;

            Debug.Log(
                "[SessionController] " +
                "Avatar reset to rest pose."
            );
        }

        currentMode =
            SessionMode.None;

        currentState =
            SessionState.Idle;

        replayStarted =
            false;

        Debug.Log(
            "[SessionController] " +
            "Session ended."
        );
    }

    // ---------------------------------------------------------------------
    // SESSION RECORDING
    // ---------------------------------------------------------------------

    private bool StartSessionRecording()
    {
        if (poseSessionRecorder == null)
        {
            Debug.LogError(
                "[SessionController] " +
                "PoseSessionRecorder reference is missing."
            );

            return false;
        }

        ApplyPatientToModules();

        poseSessionRecorder.enabled = true;

        poseSessionRecorder.StartRecording();

        if (!poseSessionRecorder.IsRecording())
        {
            Debug.LogError(
                "[SessionController] " +
                "PoseSessionRecorder did not enter recording state."
            );

            poseSessionRecorder.enabled = false;

            return false;
        }

        Debug.Log(
            "[SessionController] " +
            "Pose session recording started."
        );

        return true;
    }

    private void StopSessionRecording()
    {
        if (poseSessionRecorder == null)
        {
            return;
        }

        if (poseSessionRecorder.IsRecording())
        {
            poseSessionRecorder.StopRecording();

            Debug.Log(
                "[SessionController] " +
                "Pose session recording stopped."
            );

            string savedPath =
                poseSessionRecorder.GetCurrentFilePath();

            if (!string.IsNullOrEmpty(savedPath))
            {
                Debug.Log(
                    "[SessionController] " +
                    "Recording saved to: " +
                    savedPath
                );
            }
        }

        poseSessionRecorder.enabled = false;
    }

    // ---------------------------------------------------------------------
    // STOP REPLAY
    // ---------------------------------------------------------------------

    private void StopReplay()
    {
        if (poseSessionReplay == null)
        {
            replayStarted =
                false;

            return;
        }

        poseSessionReplay.PauseReplay();

        replayStarted =
            false;
    }

    // ---------------------------------------------------------------------
    // PYTHON LIVE ANALYSIS
    // ---------------------------------------------------------------------

    private bool StartLiveAnalysis()
    {
        if (autoResolvePythonPaths)
        {
            ResolvePythonPaths();
        }

        if (pythonProcess != null)
        {
            if (!pythonProcess.HasExited)
            {
                Debug.LogWarning(
                    "[SessionController] " +
                    "Python live analysis is already running."
                );

                return true;
            }

            pythonProcess.Dispose();

            pythonProcess =
                null;
        }

        if (string.IsNullOrWhiteSpace(
                pythonExecutable))
        {
            Debug.LogError(
                "[SessionController] " +
                "Python executable path is empty."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(
                pythonWorkingDirectory))
        {
            Debug.LogError(
                "[SessionController] " +
                "Python working directory is empty."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(
                liveAnalysisCommand))
        {
            Debug.LogError(
                "[SessionController] " +
                "Live analysis command is empty."
            );

            return false;
        }

        if (!File.Exists(
                pythonExecutable))
        {
            Debug.LogError(
                "[SessionController] " +
                "Python executable was not found:\n" +
                pythonExecutable
            );

            return false;
        }

        if (!Directory.Exists(
                pythonWorkingDirectory))
        {
            Debug.LogError(
                "[SessionController] " +
                "Python working directory was not found:\n" +
                pythonWorkingDirectory
            );

            return false;
        }

        try
        {
            DiagnosticsProcessStartInfo startInfo =
                new DiagnosticsProcessStartInfo();

            startInfo.FileName =
                pythonExecutable;

            startInfo.Arguments =
                liveAnalysisCommand;

            startInfo.WorkingDirectory =
                pythonWorkingDirectory;

            startInfo.UseShellExecute =
                false;

            startInfo.CreateNoWindow =
                false;

            startInfo.RedirectStandardOutput =
                false;

            startInfo.RedirectStandardError =
                false;

            pythonProcess =
                new DiagnosticsProcess();

            pythonProcess.StartInfo =
                startInfo;

            bool started =
                pythonProcess.Start();

            if (!started)
            {
                Debug.LogError(
                    "[SessionController] " +
                    "Python process failed to start."
                );

                pythonProcess.Dispose();

                pythonProcess =
                    null;

                return false;
            }

            Debug.Log(
                "[SessionController] " +
                "Live Analysis started."
            );

            return true;
        }
        catch (System.Exception exception)
        {
            Debug.LogError(
                "[SessionController] " +
                "Failed to start Python:\n" +
                exception.Message
            );

            if (pythonProcess != null)
            {
                pythonProcess.Dispose();

                pythonProcess =
                    null;
            }

            return false;
        }
    }

    // ---------------------------------------------------------------------
    // STOP PYTHON
    // ---------------------------------------------------------------------

    private void StopLiveAnalysis()
    {
        if (pythonProcess == null)
        {
            return;
        }

        try
        {
            if (!pythonProcess.HasExited)
            {
                Debug.Log(
                    "[SessionController] " +
                    "Stopping Live Analysis."
                );

                pythonProcess.Kill();

                pythonProcess.WaitForExit(2000);
            }
        }
        catch (System.Exception exception)
        {
            Debug.LogWarning(
                "[SessionController] " +
                "Error stopping Python: " +
                exception.Message
            );
        }
        finally
        {
            pythonProcess.Dispose();

            pythonProcess =
                null;
        }
    }

    // ---------------------------------------------------------------------
    // STATUS API
    // ---------------------------------------------------------------------

    public SessionMode GetCurrentMode()
    {
        return currentMode;
    }

    public SessionState GetCurrentState()
    {
        return currentState;
    }

    public bool IsSessionActive()
    {
        return currentState !=
               SessionState.Idle;
    }

    public bool IsLiveSession()
    {
        return currentMode ==
               SessionMode.Live;
    }

    public bool IsReplaySession()
    {
        return currentMode ==
               SessionMode.Replay;
    }

    public string GetSessionStatus()
    {
        return
            currentMode.ToString() +
            " / " +
            currentState.ToString();
    }

    // ---------------------------------------------------------------------
    // Developer GUI
    // ---------------------------------------------------------------------

    private void OnGUI()
    {
        if (!showDeveloperControls)
        {
            return;
        }

        const float panelWidth = 300f;
        const float panelHeight = 210f;

        Rect panelRect =
            new Rect(
                10f,
                Screen.height -
                panelHeight -
                10f,
                panelWidth,
                panelHeight
            );

        GUI.Box(
            panelRect,
            "RehabTwin Session Controller"
        );

        GUILayout.BeginArea(
            new Rect(
                panelRect.x + 10f,
                panelRect.y + 25f,
                panelRect.width - 20f,
                panelRect.height - 30f
            )
        );

        GUILayout.Label(
            "Patient: " +
            patientId
        );

        GUILayout.Label(
            "Mode: " +
            currentMode
        );

        GUILayout.Label(
            "State: " +
            currentState
        );

        GUILayout.Space(8f);

        GUI.enabled =
            currentState ==
            SessionState.Idle;

        if (GUILayout.Button(
                "START LIVE",
                GUILayout.Height(28f)))
        {
            StartLiveSession();
        }

        if (GUILayout.Button(
                "START REPLAY",
                GUILayout.Height(28f)))
        {
            StartReplaySession();
        }

        GUI.enabled =
            currentState !=
            SessionState.Idle;

        if (GUILayout.Button(
                "END SESSION",
                GUILayout.Height(28f)))
        {
            EndCurrentSession();
        }

        GUI.enabled = true;

        GUILayout.EndArea();
    }
}