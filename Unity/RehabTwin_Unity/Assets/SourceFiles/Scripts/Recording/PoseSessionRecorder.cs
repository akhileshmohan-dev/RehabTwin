using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[Serializable]
public class RecordedPoseFrame
{
    public float time;
    public PoseFrame pose;
}

[Serializable]
public class PoseSession
{
    public string sessionId;
    public string patientId;
    public string createdAt;
    public float duration;
    public int frameCount;

    public List<RecordedPoseFrame> frames =
        new List<RecordedPoseFrame>();
}

public class PoseSessionRecorder : MonoBehaviour
{
    // ---------------------------------------------------------------------
    // References
    // ---------------------------------------------------------------------

    [Header("References")]
    public PoseReceiver poseReceiver;

    // ---------------------------------------------------------------------
    // Recording
    // ---------------------------------------------------------------------

    [Header("Recording")]
    [Range(5f, 60f)]
    public float recordingFrameRate = 30f;

    // ---------------------------------------------------------------------
    // Patient
    // ---------------------------------------------------------------------

    [Header("Patient")]
    public string patientId = "";

    // ---------------------------------------------------------------------
    // Runtime
    // ---------------------------------------------------------------------

    private PoseSession currentSession;

    private bool recording = false;

    private float recordingStartTime = 0f;

    private float lastRecordedTime = -1f;

    private string currentFilePath = "";

    // Tracks whether the first actual valid pose has been recorded.
    private bool hasRecordedFirstFrame = false;

    // ---------------------------------------------------------------------
    // Unity
    // ---------------------------------------------------------------------

    private void Awake()
    {
        Debug.Log(
            "[PoseRecorder] Ready."
        );
    }

    private void Update()
    {
        if (!recording)
            return;

        RecordCurrentPose();
    }

    // ---------------------------------------------------------------------
    // PATIENT
    // ---------------------------------------------------------------------

    public bool SetPatient(
        string newPatientId
    )
    {
        if (recording)
        {
            Debug.LogWarning(
                "[PoseRecorder] " +
                "Cannot change patient while recording."
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(newPatientId))
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "Patient ID cannot be empty."
            );

            return false;
        }

        patientId =
            newPatientId.Trim().ToUpper();

        Debug.Log(
            "[PoseRecorder] " +
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
    // START RECORDING
    // ---------------------------------------------------------------------

    public void StartRecording()
    {
        if (recording)
        {
            Debug.LogWarning(
                "[PoseRecorder] " +
                "Already recording."
            );

            return;
        }

        if (poseReceiver == null)
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "PoseReceiver reference is missing."
            );

            return;
        }

        if (string.IsNullOrWhiteSpace(patientId))
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "Patient ID is not set."
            );

            return;
        }

        if (!RehabTwinPathResolver.ValidateStructure(
                out string pathError))
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "RehabTwin storage structure is invalid:\n" +
                pathError
            );

            return;
        }

        currentSession =
            new PoseSession();

        currentSession.sessionId =
            Guid.NewGuid().ToString();

        currentSession.patientId =
            patientId;

        currentSession.createdAt =
            DateTime.Now.ToString(
                "yyyy-MM-dd_HH-mm-ss"
            );

        // The actual recording clock starts when
        // the first valid pose is captured.
        recordingStartTime = 0f;

        lastRecordedTime = -1f;

        hasRecordedFirstFrame = false;

        currentFilePath =
            CreateSessionPath(
                currentSession
            );

        recording = true;

        Debug.Log(
            "[PoseRecorder] " +
            "Recording started."
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Patient ID: " +
            currentSession.patientId
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Session ID: " +
            currentSession.sessionId
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Waiting for first valid pose..."
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Output: " +
            currentFilePath
        );
    }

    // ---------------------------------------------------------------------
    // RECORD CURRENT POSE
    // ---------------------------------------------------------------------

    private void RecordCurrentPose()
    {
        if (poseReceiver == null)
            return;

        PoseFrame pose =
            poseReceiver.LatestPose;

        if (pose == null)
            return;

        if (pose.landmarks == null)
            return;

        float currentTime;

        // -------------------------------------------------------------
        // First valid pose
        // -------------------------------------------------------------

        if (!hasRecordedFirstFrame)
        {
            recordingStartTime =
                Time.time;

            currentTime = 0f;

            hasRecordedFirstFrame = true;
        }
        else
        {
            currentTime =
                Time.time -
                recordingStartTime;
        }

        // -------------------------------------------------------------
        // Frame-rate limiting
        // -------------------------------------------------------------

        float minimumInterval =
            1f /
            recordingFrameRate;

        if (
            lastRecordedTime >= 0f &&
            currentTime - lastRecordedTime <
            minimumInterval
        )
        {
            return;
        }

        // -------------------------------------------------------------
        // Clone pose
        // -------------------------------------------------------------

        PoseFrame clonedPose =
            ClonePose(pose);

        if (clonedPose == null)
            return;

        // -------------------------------------------------------------
        // Create recorded frame
        // -------------------------------------------------------------

        RecordedPoseFrame frame =
            new RecordedPoseFrame();

        frame.time =
            currentTime;

        frame.pose =
            clonedPose;

        currentSession.frames.Add(
            frame
        );

        lastRecordedTime =
            currentTime;
    }

    // ---------------------------------------------------------------------
    // STOP RECORDING
    // ---------------------------------------------------------------------

    public void StopRecording()
    {
        if (!recording)
        {
            Debug.LogWarning(
                "[PoseRecorder] " +
                "Not currently recording."
            );

            return;
        }

        recording = false;

        if (currentSession == null)
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "Current session is missing."
            );

            return;
        }

        // -------------------------------------------------------------
        // No valid pose was ever recorded
        // -------------------------------------------------------------

        if (!hasRecordedFirstFrame)
        {
            currentSession.duration = 0f;
            currentSession.frameCount = 0;

            Debug.LogWarning(
                "[PoseRecorder] " +
                "No valid pose frames were recorded."
            );
        }
        else
        {
            currentSession.duration =
                Time.time -
                recordingStartTime;

            currentSession.frameCount =
                currentSession.frames.Count;
        }

        SaveSession();

        Debug.Log(
            "[PoseRecorder] " +
            "Recording stopped."
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Patient: " +
            currentSession.patientId
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Frames: " +
            currentSession.frameCount
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Duration: " +
            currentSession.duration.ToString(
                "F2"
            ) +
            " seconds"
        );

        Debug.Log(
            "[PoseRecorder] " +
            "Saved to: " +
            currentFilePath
        );
    }

    // ---------------------------------------------------------------------
    // SAVE SESSION
    // ---------------------------------------------------------------------

    private void SaveSession()
    {
        if (currentSession == null)
            return;

        if (string.IsNullOrEmpty(
                currentFilePath))
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "Session file path is empty."
            );

            return;
        }

        string directory =
            Path.GetDirectoryName(
                currentFilePath
            );

        if (string.IsNullOrEmpty(directory))
        {
            Debug.LogError(
                "[PoseRecorder] " +
                "Invalid session directory."
            );

            return;
        }

        if (!Directory.Exists(directory))
        {
            Directory.CreateDirectory(
                directory
            );
        }

        string json =
            JsonUtility.ToJson(
                currentSession,
                true
            );

        File.WriteAllText(
            currentFilePath,
            json
        );
    }

    // ---------------------------------------------------------------------
    // CREATE FILE PATH
    // ---------------------------------------------------------------------

    private string CreateSessionPath(
        PoseSession session
    )
    {
        string sessionsDirectory =
            RehabTwinPathResolver
                .GetPatientSessionsRoot(
                    session.patientId
                );

        if (!Directory.Exists(
                sessionsDirectory))
        {
            Directory.CreateDirectory(
                sessionsDirectory
            );
        }

        string fileName =
            "Session_" +
            session.createdAt +
            "_" +
            session.sessionId.Substring(
                0,
                8
            ) +
            ".json";

        return Path.Combine(
            sessionsDirectory,
            fileName
        );
    }

    // ---------------------------------------------------------------------
    // CLONE POSE
    // ---------------------------------------------------------------------

    private PoseFrame ClonePose(
        PoseFrame source
    )
    {
        if (
            source == null ||
            source.landmarks == null
        )
        {
            return null;
        }

        PoseFrame clone =
            new PoseFrame();

        clone.landmarks =
            new PoseLandmark[
                source.landmarks.Length
            ];

        for (
            int i = 0;
            i < source.landmarks.Length;
            i++
        )
        {
            PoseLandmark sourceLandmark =
                source.landmarks[i];

            if (sourceLandmark == null)
                continue;

            PoseLandmark landmark =
                new PoseLandmark();

            landmark.name =
                sourceLandmark.name;

            landmark.x =
                sourceLandmark.x;

            landmark.y =
                sourceLandmark.y;

            landmark.z =
                sourceLandmark.z;

            landmark.visibility =
                sourceLandmark.visibility;

            landmark.world_x =
                sourceLandmark.world_x;

            landmark.world_y =
                sourceLandmark.world_y;

            landmark.world_z =
                sourceLandmark.world_z;

            clone.landmarks[i] =
                landmark;
        }

        clone.BuildLookup();

        return clone;
    }

    // ---------------------------------------------------------------------
    // STATUS
    // ---------------------------------------------------------------------

    public bool IsRecording()
    {
        return recording;
    }

    public int GetRecordedFrameCount()
    {
        if (currentSession == null)
            return 0;

        return currentSession.frames.Count;
    }

    public float GetRecordingDuration()
    {
        if (
            !recording ||
            currentSession == null ||
            !hasRecordedFirstFrame
        )
        {
            return 0f;
        }

        return
            Time.time -
            recordingStartTime;
    }

    public string GetCurrentFilePath()
    {
        return currentFilePath;
    }
}