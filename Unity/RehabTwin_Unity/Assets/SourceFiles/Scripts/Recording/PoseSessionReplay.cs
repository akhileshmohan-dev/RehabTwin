using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;

public class PoseSessionReplay : MonoBehaviour
{
    // ---------------------------------------------------------------------
    // References
    // ---------------------------------------------------------------------

    [Header("References")]
    public PoseReceiver poseReceiver;

    public AvatarTrackingController avatarTrackingController;

    // ---------------------------------------------------------------------
    // Replay
    // ---------------------------------------------------------------------

    [Header("Replay")]
    public bool loadLatestSessionOnStart = false;
    public bool playOnLoad = false;

    // ---------------------------------------------------------------------
    // Patient
    // ---------------------------------------------------------------------

    [Header("Patient")]
    [Tooltip("Patient whose sessions will be replayed.")]
    public string patientId = "";

    // ---------------------------------------------------------------------
    // Controls
    // ---------------------------------------------------------------------

    [Header("Controls")]
    public bool allowKeyboardControls = true;

    // ---------------------------------------------------------------------
    // Runtime
    // ---------------------------------------------------------------------

    private PoseSession session;

    private int currentFrameIndex = 0;

    private float replayTime = 0f;

    private bool playing = false;

    private string loadedFilePath = "";

    // ---------------------------------------------------------------------
    // Unity
    // ---------------------------------------------------------------------

    private void Awake()
    {
        Debug.Log(
            "[PoseReplay] Ready."
        );
    }

    private void Start()
    {
        if (loadLatestSessionOnStart)
        {
            LoadLatestSession();

            if (playOnLoad)
            {
                StartReplay();
            }
        }
    }

    private void Update()
    {
        HandleKeyboardInput();

        if (!playing)
            return;

        UpdateReplay();
    }

    // ---------------------------------------------------------------------
    // PATIENT
    // ---------------------------------------------------------------------

    public bool SetPatient(
        string newPatientId
    )
    {
        if (playing)
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "Cannot change patient during replay."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(newPatientId))
        {
            Debug.LogError(
                "[PoseReplay] " +
                "Patient ID cannot be empty."
            );

            return false;
        }

        patientId =
            newPatientId.Trim().ToUpper();

        // Clear any previously loaded session because
        // it may belong to a different patient.
        session = null;
        loadedFilePath = "";
        currentFrameIndex = 0;
        replayTime = 0f;
        playing = false;

        Debug.Log(
            "[PoseReplay] " +
            "Patient set to: " +
            patientId
        );

        return true;
    }

    public string GetPatientId()
    {
        return patientId;
    }

    // ---------------------------------------------------------------------
    // KEYBOARD
    // ---------------------------------------------------------------------

    private void HandleKeyboardInput()
    {
        if (!allowKeyboardControls)
            return;

        if (Keyboard.current == null)
            return;

        // P = Play / Pause
        if (Keyboard.current.pKey.wasPressedThisFrame)
        {
            if (playing)
                PauseReplay();
            else
                StartReplay();
        }

        // L = Load latest session
        if (Keyboard.current.lKey.wasPressedThisFrame)
        {
            LoadLatestSession();
        }

        // R = Restart replay
        if (Keyboard.current.rKey.wasPressedThisFrame)
        {
            RestartReplay();
        }
    }

    // ---------------------------------------------------------------------
    // LOAD LATEST SESSION
    // ---------------------------------------------------------------------

    public void LoadLatestSession()
    {
        if (string.IsNullOrWhiteSpace(patientId))
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "Patient ID is not set."
            );

            return;
        }

        if (!RehabTwinPathResolver.ValidateStructure(
                out string pathError))
        {
            Debug.LogError(
                "[PoseReplay] " +
                "RehabTwin storage structure is invalid:\n" +
                pathError
            );

            return;
        }

        string directory;

        try
        {
            directory =
                RehabTwinPathResolver
                    .GetPatientSessionsRoot(
                        patientId
                    );
        }
        catch (System.Exception exception)
        {
            Debug.LogError(
                "[PoseReplay] " +
                "Could not resolve patient session path:\n" +
                exception.Message
            );

            return;
        }

        if (!Directory.Exists(directory))
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "Patient sessions folder does not exist:\n" +
                directory
            );

            return;
        }

        string[] files =
            Directory.GetFiles(
                directory,
                "Session_*.json"
            );

        if (files == null ||
            files.Length == 0)
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "No recorded sessions found for patient: " +
                patientId
            );

            return;
        }

        string latestFile =
            files[0];

        for (
            int i = 1;
            i < files.Length;
            i++
        )
        {
            if (
                File.GetLastWriteTime(
                    files[i]
                )
                >
                File.GetLastWriteTime(
                    latestFile
                )
            )
            {
                latestFile =
                    files[i];
            }
        }

        LoadSession(
            latestFile
        );
    }

    // ---------------------------------------------------------------------
    // LOAD SESSION
    // ---------------------------------------------------------------------

    public void LoadSession(
        string filePath
    )
    {
        if (!File.Exists(filePath))
        {
            Debug.LogError(
                "[PoseReplay] " +
                "Session file not found: " +
                filePath
            );

            return;
        }

        try
        {
            string json =
                File.ReadAllText(
                    filePath
                );

            PoseSession loadedSession =
                JsonUtility.FromJson<PoseSession>(
                    json
                );

            if (loadedSession == null)
            {
                Debug.LogError(
                    "[PoseReplay] " +
                    "Failed to deserialize session."
                );

                return;
            }

            if (
                loadedSession.frames == null ||
                loadedSession.frames.Count == 0
            )
            {
                Debug.LogError(
                    "[PoseReplay] " +
                    "Session contains no frames."
                );

                return;
            }

            // Make sure the loaded session belongs
            // to the selected patient.
            if (
                !string.IsNullOrEmpty(
                    loadedSession.patientId
                ) &&
                !string.Equals(
                    loadedSession.patientId,
                    patientId,
                    System.StringComparison.OrdinalIgnoreCase
                )
            )
            {
                Debug.LogError(
                    "[PoseReplay] " +
                    "Session belongs to patient '" +
                    loadedSession.patientId +
                    "' but replay is set to patient '" +
                    patientId +
                    "'."
                );

                return;
            }

            session =
                loadedSession;

            loadedFilePath =
                filePath;

            currentFrameIndex = 0;

            replayTime = 0f;

            playing = false;

            Debug.Log(
                "[PoseReplay] " +
                "Session loaded."
            );

            Debug.Log(
                "[PoseReplay] " +
                "Patient: " +
                session.patientId
            );

            Debug.Log(
                "[PoseReplay] " +
                "Frames: " +
                session.frames.Count
            );

            Debug.Log(
                "[PoseReplay] " +
                "Duration: " +
                session.duration.ToString(
                    "F2"
                ) +
                " seconds"
            );

            Debug.Log(
                "[PoseReplay] " +
                "File: " +
                loadedFilePath
            );
        }
        catch (System.Exception exception)
        {
            Debug.LogError(
                "[PoseReplay] " +
                "Error loading session: " +
                exception.Message
            );
        }
    }

    // ---------------------------------------------------------------------
    // START REPLAY
    // ---------------------------------------------------------------------

    public void StartReplay()
    {
        if (session == null)
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "No session loaded."
            );

            return;
        }

        if (
            session.frames == null ||
            session.frames.Count == 0
        )
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "Session has no frames."
            );

            return;
        }

        if (
            currentFrameIndex >=
            session.frames.Count
        )
        {
            RestartReplay();
        }

        playing = true;

        Debug.Log(
            "[PoseReplay] " +
            "Replay started."
        );
    }

    // ---------------------------------------------------------------------
    // PAUSE
    // ---------------------------------------------------------------------

    public void PauseReplay()
    {
        playing = false;

        Debug.Log(
            "[PoseReplay] " +
            "Replay paused."
        );
    }

    // ---------------------------------------------------------------------
    // RESTART
    // ---------------------------------------------------------------------

    public void RestartReplay()
    {
        if (session == null)
        {
            Debug.LogWarning(
                "[PoseReplay] " +
                "No session loaded."
            );

            return;
        }

        currentFrameIndex = 0;

        replayTime = 0f;

        playing = false;

        Debug.Log(
            "[PoseReplay] " +
            "Replay reset."
        );
    }

    // ---------------------------------------------------------------------
    // REPLAY UPDATE
    // ---------------------------------------------------------------------

    private void UpdateReplay()
    {
        if (session == null)
            return;

        if (
            session.frames == null ||
            session.frames.Count == 0
        )
        {
            playing = false;
            return;
        }

        replayTime +=
            Time.deltaTime;

        while (
            currentFrameIndex <
            session.frames.Count
        )
        {
            RecordedPoseFrame frame =
                session.frames[
                    currentFrameIndex
                ];

            if (
                frame == null ||
                frame.pose == null
            )
            {
                currentFrameIndex++;
                continue;
            }

            if (
                frame.time >
                replayTime
            )
            {
                break;
            }

            InjectFrame(
                frame
            );

            currentFrameIndex++;
        }

        if (
            currentFrameIndex >=
            session.frames.Count
        )
        {
            playing = false;

            Debug.Log(
                "[PoseReplay] " +
                "Replay finished."
            );
        }
    }

    // ---------------------------------------------------------------------
    // INJECT FRAME
    // ---------------------------------------------------------------------

    private void InjectFrame(
        RecordedPoseFrame frame
    )
    {
        if (poseReceiver == null)
            return;

        if (frame == null)
            return;

        if (frame.pose == null)
            return;

        poseReceiver.SetReplayPose(
            frame.pose
        );
    }

    // ---------------------------------------------------------------------
    // STATUS
    // ---------------------------------------------------------------------

    public bool IsPlaying()
    {
        return playing;
    }

    public bool HasSessionLoaded()
    {
        return session != null;
    }

    public int GetCurrentFrame()
    {
        return currentFrameIndex;
    }

    public int GetTotalFrames()
    {
        if (
            session == null ||
            session.frames == null
        )
        {
            return 0;
        }

        return session.frames.Count;
    }

    public float GetReplayTime()
    {
        return replayTime;
    }

    public float GetDuration()
    {
        if (session == null)
            return 0f;

        return session.duration;
    }

    public string GetLoadedFilePath()
    {
        return loadedFilePath;
    }
}