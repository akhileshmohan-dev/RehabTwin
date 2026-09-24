using UnityEngine;

public class PoseCalibrator
{
    public enum CalibrationState
    {
        Waiting,
        Stabilizing,
        Calibrated
    }

    // =========================================================
    // SETTINGS
    // =========================================================

    private readonly int requiredStableFrames;

    private readonly float visibilityThreshold;

    private readonly float stabilityThreshold;

    // =========================================================
    // STATE
    // =========================================================

    private CalibrationState state =
        CalibrationState.Waiting;

    private int stableFrameCount = 0;

    private Vector3 referenceHipCenter;
    private Vector3 referenceShoulderCenter;

    private float referenceShoulderWidth;
    private float referenceTorsoLength;

    private PoseFrame previousPose;

    // =========================================================
    // CONSTRUCTOR
    // =========================================================

    public PoseCalibrator(
        int requiredStableFrames = 15,
        float visibilityThreshold = 0.5f,
        float stabilityThreshold = 0.015f)
    {
        this.requiredStableFrames =
            requiredStableFrames;

        this.visibilityThreshold =
            visibilityThreshold;

        this.stabilityThreshold =
            stabilityThreshold;
    }

    // =========================================================
    // PROCESS
    // =========================================================

    public bool Update(
        PoseFrame pose)
    {
        if (pose == null ||
            pose.landmarks == null)
        {
            stableFrameCount = 0;

            state =
                CalibrationState.Waiting;

            return false;
        }

        pose.BuildLookup();

        // -----------------------------------------------------
        // REQUIRE COMPLETE BODY
        // -----------------------------------------------------

        if (pose.landmarks.Length != 33)
        {
            stableFrameCount = 0;

            state =
                CalibrationState.Waiting;

            return false;
        }

        // -----------------------------------------------------
        // CHECK REQUIRED LANDMARKS
        // -----------------------------------------------------

        if (!HasRequiredLandmarks(pose))
        {
            stableFrameCount = 0;

            state =
                CalibrationState.Waiting;

            return false;
        }

        // -----------------------------------------------------
        // FIRST VALID FRAME
        // -----------------------------------------------------

        if (previousPose == null)
        {
            previousPose =
                ClonePose(pose);

            stableFrameCount = 1;

            state =
                CalibrationState.Stabilizing;

            return false;
        }

        // -----------------------------------------------------
        // CHECK STABILITY
        // -----------------------------------------------------

        if (!IsStable(
            previousPose,
            pose))
        {
            stableFrameCount = 0;

            previousPose =
                ClonePose(pose);

            state =
                CalibrationState.Stabilizing;

            return false;
        }

        stableFrameCount++;

        previousPose =
            ClonePose(pose);

        state =
            CalibrationState.Stabilizing;

        // -----------------------------------------------------
        // CALIBRATE
        // -----------------------------------------------------

        if (stableFrameCount >=
            requiredStableFrames)
        {
            CaptureReference(pose);

            state =
                CalibrationState.Calibrated;

            return true;
        }

        return false;
    }

    // =========================================================
    // REQUIRED LANDMARKS
    // =========================================================

    private bool HasRequiredLandmarks(
        PoseFrame pose)
    {
        string[] required =
        {
            "NOSE",

            "LEFT_SHOULDER",
            "RIGHT_SHOULDER",

            "LEFT_ELBOW",
            "RIGHT_ELBOW",

            "LEFT_WRIST",
            "RIGHT_WRIST",

            "LEFT_HIP",
            "RIGHT_HIP",

            "LEFT_KNEE",
            "RIGHT_KNEE",

            "LEFT_ANKLE",
            "RIGHT_ANKLE"
        };

        foreach (
            string name
            in required)
        {
            PoseLandmark landmark;

            if (!pose.TryGetLandmark(
                name,
                out landmark))
            {
                return false;
            }

            if (landmark == null)
                return false;

            if (landmark.visibility <
                visibilityThreshold)
            {
                return false;
            }
        }

        return true;
    }

    // =========================================================
    // STABILITY
    // =========================================================

    private bool IsStable(
        PoseFrame previous,
        PoseFrame current)
    {
        Vector3 previousHipCenter =
            GetMidpoint(
                previous,
                "LEFT_HIP",
                "RIGHT_HIP"
            );

        Vector3 currentHipCenter =
            GetMidpoint(
                current,
                "LEFT_HIP",
                "RIGHT_HIP"
            );

        Vector3 previousShoulderCenter =
            GetMidpoint(
                previous,
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            );

        Vector3 currentShoulderCenter =
            GetMidpoint(
                current,
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            );

        float bodyScale =
            GetBodyScale(current);

        if (bodyScale <= 0.0001f)
            return false;

        float hipMovement =
            Vector3.Distance(
                previousHipCenter,
                currentHipCenter
            ) / bodyScale;

        float shoulderMovement =
            Vector3.Distance(
                previousShoulderCenter,
                currentShoulderCenter
            ) / bodyScale;

        /*
         * We deliberately measure movement relative to body size.
         *
         * This prevents camera distance from directly determining
         * whether the person is considered stable.
         */

        if (hipMovement >
            stabilityThreshold)
        {
            return false;
        }

        if (shoulderMovement >
            stabilityThreshold)
        {
            return false;
        }

        return true;
    }

    // =========================================================
    // CAPTURE REFERENCE
    // =========================================================

    private void CaptureReference(
        PoseFrame pose)
    {
        referenceHipCenter =
            GetMidpoint(
                pose,
                "LEFT_HIP",
                "RIGHT_HIP"
            );

        referenceShoulderCenter =
            GetMidpoint(
                pose,
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            );

        referenceShoulderWidth =
            GetDistance(
                pose,
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            );

        referenceTorsoLength =
            Vector3.Distance(
                referenceHipCenter,
                referenceShoulderCenter
            );
    }

    // =========================================================
    // BODY SCALE
    // =========================================================

    private float GetBodyScale(
        PoseFrame pose)
    {
        float shoulderWidth =
            GetDistance(
                pose,
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER"
            );

        float torsoLength =
            Vector3.Distance(
                GetMidpoint(
                    pose,
                    "LEFT_HIP",
                    "RIGHT_HIP"
                ),
                GetMidpoint(
                    pose,
                    "LEFT_SHOULDER",
                    "RIGHT_SHOULDER"
                )
            );

        return Mathf.Max(
            shoulderWidth,
            torsoLength
        );
    }

    // =========================================================
    // POSITION
    // =========================================================

    private Vector3 GetPosition(
        PoseFrame pose,
        string name)
    {
        PoseLandmark landmark;

        if (!pose.TryGetLandmark(
            name,
            out landmark))
        {
            return Vector3.zero;
        }

        if (landmark == null)
            return Vector3.zero;

        return new Vector3(
            landmark.world_x,
            landmark.world_y,
            landmark.world_z
        );
    }

    // =========================================================
    // MIDPOINT
    // =========================================================

    private Vector3 GetMidpoint(
        PoseFrame pose,
        string first,
        string second)
    {
        Vector3 a =
            GetPosition(
                pose,
                first
            );

        Vector3 b =
            GetPosition(
                pose,
                second
            );

        return (a + b) * 0.5f;
    }

    // =========================================================
    // DISTANCE
    // =========================================================

    private float GetDistance(
        PoseFrame pose,
        string first,
        string second)
    {
        Vector3 a =
            GetPosition(
                pose,
                first
            );

        Vector3 b =
            GetPosition(
                pose,
                second
            );

        return Vector3.Distance(
            a,
            b
        );
    }

    // =========================================================
    // CLONE POSE
    // =========================================================

    private PoseFrame ClonePose(
        PoseFrame source)
    {
        PoseFrame clone =
            new PoseFrame();

        if (source == null ||
            source.landmarks == null)
        {
            clone.landmarks =
                new PoseLandmark[0];

            clone.BuildLookup();

            return clone;
        }

        clone.landmarks =
            new PoseLandmark[
                source.landmarks.Length
            ];

        for (
            int i = 0;
            i < source.landmarks.Length;
            i++)
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

    // =========================================================
    // PUBLIC ACCESS
    // =========================================================

    public CalibrationState State
    {
        get
        {
            return state;
        }
    }

    public bool IsCalibrated
    {
        get
        {
            return state ==
                   CalibrationState.Calibrated;
        }
    }

    public int StableFrameCount
    {
        get
        {
            return stableFrameCount;
        }
    }

    public Vector3 ReferenceHipCenter
    {
        get
        {
            return referenceHipCenter;
        }
    }

    public Vector3 ReferenceShoulderCenter
    {
        get
        {
            return referenceShoulderCenter;
        }
    }

    public float ReferenceShoulderWidth
    {
        get
        {
            return referenceShoulderWidth;
        }
    }

    public float ReferenceTorsoLength
    {
        get
        {
            return referenceTorsoLength;
        }
    }

    // =========================================================
    // RESET
    // =========================================================

    public void Reset()
    {
        stableFrameCount = 0;

        previousPose = null;

        state =
            CalibrationState.Waiting;

        referenceHipCenter =
            Vector3.zero;

        referenceShoulderCenter =
            Vector3.zero;

        referenceShoulderWidth =
            0f;

        referenceTorsoLength =
            0f;
    }
}