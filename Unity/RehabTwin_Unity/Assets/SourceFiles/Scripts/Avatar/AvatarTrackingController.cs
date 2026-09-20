using UnityEngine;

public class AvatarTrackingController : MonoBehaviour
{
    [Header("References")]
    public PoseReceiver poseReceiver;
    public BoneMap boneMap;

    [Header("Processing")]
    public bool useWorldCoordinates = true;
    public bool mirrorX = true;

    [Header("Movement")]
    [Range(0.01f, 1f)]
    public float rotationSmoothness = 0.2f;

    [Header("Visibility")]
    [Range(0f, 1f)]
    public float minimumVisibility = 0.5f;

    [Header("Tracking Quality")]
    [Range(1, 30)]
    public int maximumHeldFrames = 8;

    [Header("Calibration")]
    public int requiredStableFrames = 15;

    [Range(0.001f, 0.1f)]
    public float calibrationStabilityThreshold = 0.015f;

    [Header("Debug")]
    public bool enableDebugLogs = true;
    public int debugIntervalFrames = 60;

    private PoseProcessor poseProcessor;
    private PoseCalibrator poseCalibrator;

    private PoseFrame currentPose;

    private int debugFrameCounter = 0;

    private bool calibrated = false;

    // =========================================================
    // TRACKING STATE
    // =========================================================

    private int bodyInvalidFrames = 0;

    private int leftArmInvalidFrames = 0;
    private int rightArmInvalidFrames = 0;

    private int leftLegInvalidFrames = 0;
    private int rightLegInvalidFrames = 0;

    private bool bodyTrackingAvailable = false;

    // =========================================================
    // ORIGINAL MIXAMO ROTATIONS
    // =========================================================

    private Quaternion initialSpineRotation;

    private Quaternion initialLeftUpperArmRotation;
    private Quaternion initialLeftForeArmRotation;

    private Quaternion initialRightUpperArmRotation;
    private Quaternion initialRightForeArmRotation;

    private Quaternion initialLeftUpperLegRotation;
    private Quaternion initialLeftLowerLegRotation;

    private Quaternion initialRightUpperLegRotation;
    private Quaternion initialRightLowerLegRotation;

    // =========================================================
    // ORIGINAL BONE DIRECTIONS
    // =========================================================

    private Vector3 initialSpineDirection;

    private Vector3 initialLeftUpperArmDirection;
    private Vector3 initialLeftForeArmDirection;

    private Vector3 initialRightUpperArmDirection;
    private Vector3 initialRightForeArmDirection;

    private Vector3 initialLeftUpperLegDirection;
    private Vector3 initialLeftLowerLegDirection;

    private Vector3 initialRightUpperLegDirection;
    private Vector3 initialRightLowerLegDirection;

    // =========================================================
    // UNITY
    // =========================================================

    private void Awake()
    {
        poseProcessor =
            new PoseProcessor();

        poseProcessor.mirrorX =
            mirrorX;

        poseCalibrator =
            new PoseCalibrator(
                requiredStableFrames,
                minimumVisibility,
                calibrationStabilityThreshold
            );

        Debug.Log(
            "[AvatarTracking] Awake"
        );
    }

    private void Start()
    {
        CaptureRestPose();
    }

    private void Update()
    {
        debugFrameCounter++;

        // -----------------------------------------------------
        // REFERENCES
        // -----------------------------------------------------

        if (poseReceiver == null)
        {
            DebugMessage(
                "STOP: PoseReceiver reference is NULL."
            );

            return;
        }

        if (boneMap == null)
        {
            DebugMessage(
                "STOP: BoneMap reference is NULL."
            );

            return;
        }

        if (!boneMap.IsValid())
        {
            DebugMessage(
                "STOP: BoneMap is NOT valid."
            );

            return;
        }

        // -----------------------------------------------------
        // RAW POSE
        // -----------------------------------------------------

        PoseFrame rawPose =
            poseReceiver.LatestPose;

        if (rawPose == null)
        {
            bodyInvalidFrames++;

            DebugMessage(
                "WAITING: LatestPose is NULL."
            );

            return;
        }

        if (rawPose.landmarks == null)
        {
            bodyInvalidFrames++;

            DebugMessage(
                "WAITING: LatestPose.landmarks is NULL."
            );

            return;
        }

        // -----------------------------------------------------
        // PROCESS POSE
        // -----------------------------------------------------

        currentPose =
            poseProcessor.Process(
                rawPose
            );

        if (currentPose == null)
        {
            bodyInvalidFrames++;

            DebugMessage(
                "STOP: PoseProcessor returned NULL."
            );

            return;
        }

        currentPose.BuildLookup();

        // -----------------------------------------------------
        // CALIBRATION
        // -----------------------------------------------------

        if (!calibrated)
        {
            bool calibrationComplete =
                poseCalibrator.Update(
                    currentPose
                );

            DebugMessage(
                "CALIBRATION: " +
                poseCalibrator.State +
                " | stable=" +
                poseCalibrator.StableFrameCount +
                "/" +
                requiredStableFrames
            );

            if (!calibrationComplete)
            {
                return;
            }

            calibrated = true;

            Debug.Log(
                "[AvatarTracking] " +
                "Calibration complete. " +
                "Avatar tracking enabled."
            );
        }

        // -----------------------------------------------------
        // UPDATE EACH SYSTEM INDEPENDENTLY
        // -----------------------------------------------------

        UpdateArms();

        UpdateSpine();

        UpdateLegs();

        UpdateTrackingState();
    }

    // =========================================================
    // TRACKING STATE
    // =========================================================

    private void UpdateTrackingState()
    {
        bool bodyValid =
            HasUsable(
                "LEFT_SHOULDER"
            ) &&
            HasUsable(
                "RIGHT_SHOULDER"
            ) &&
            HasUsable(
                "LEFT_HIP"
            ) &&
            HasUsable(
                "RIGHT_HIP"
            );

        if (bodyValid)
        {
            bodyInvalidFrames = 0;
            bodyTrackingAvailable = true;
        }
        else
        {
            bodyInvalidFrames++;

            if (bodyInvalidFrames >
                maximumHeldFrames)
            {
                bodyTrackingAvailable = false;
            }
        }
    }

    // =========================================================
    // CAPTURE MIXAMO REST POSE
    // =========================================================

    private void CaptureRestPose()
    {
        if (boneMap == null)
        {
            Debug.LogWarning(
                "[AvatarTracking] " +
                "Cannot capture rest pose: BoneMap missing."
            );

            return;
        }

        // -----------------------------------------------------
        // ORIGINAL ROTATIONS
        // -----------------------------------------------------

        if (boneMap.spine != null)
            initialSpineRotation =
                boneMap.spine.rotation;

        if (boneMap.leftUpperArm != null)
            initialLeftUpperArmRotation =
                boneMap.leftUpperArm.rotation;

        if (boneMap.leftForeArm != null)
            initialLeftForeArmRotation =
                boneMap.leftForeArm.rotation;

        if (boneMap.rightUpperArm != null)
            initialRightUpperArmRotation =
                boneMap.rightUpperArm.rotation;

        if (boneMap.rightForeArm != null)
            initialRightForeArmRotation =
                boneMap.rightForeArm.rotation;

        if (boneMap.leftUpperLeg != null)
            initialLeftUpperLegRotation =
                boneMap.leftUpperLeg.rotation;

        if (boneMap.leftLowerLeg != null)
            initialLeftLowerLegRotation =
                boneMap.leftLowerLeg.rotation;

        if (boneMap.rightUpperLeg != null)
            initialRightUpperLegRotation =
                boneMap.rightUpperLeg.rotation;

        if (boneMap.rightLowerLeg != null)
            initialRightLowerLegRotation =
                boneMap.rightLowerLeg.rotation;

        // -----------------------------------------------------
        // ORIGINAL DIRECTIONS
        // -----------------------------------------------------

        initialSpineDirection =
            GetBoneDirection(
                boneMap.spine,
                boneMap.spine1
            );

        initialLeftUpperArmDirection =
            GetBoneDirection(
                boneMap.leftUpperArm,
                boneMap.leftForeArm
            );

        initialLeftForeArmDirection =
            GetBoneDirection(
                boneMap.leftForeArm,
                boneMap.leftHand
            );

        initialRightUpperArmDirection =
            GetBoneDirection(
                boneMap.rightUpperArm,
                boneMap.rightForeArm
            );

        initialRightForeArmDirection =
            GetBoneDirection(
                boneMap.rightForeArm,
                boneMap.rightHand
            );

        initialLeftUpperLegDirection =
            GetBoneDirection(
                boneMap.leftUpperLeg,
                boneMap.leftLowerLeg
            );

        initialLeftLowerLegDirection =
            GetBoneDirection(
                boneMap.leftLowerLeg,
                boneMap.leftFoot
            );

        initialRightUpperLegDirection =
            GetBoneDirection(
                boneMap.rightUpperLeg,
                boneMap.rightLowerLeg
            );

        initialRightLowerLegDirection =
            GetBoneDirection(
                boneMap.rightLowerLeg,
                boneMap.rightFoot
            );

        Debug.Log(
            "[AvatarTracking] " +
            "Mixamo rest pose captured."
        );
    }

    // =========================================================
    // RESET AVATAR TO REST POSE
    // =========================================================

    public void ResetAvatarToRestPose()
    {
        if (boneMap == null)
        {
            Debug.LogWarning(
                "[AvatarTracking] " +
                "Cannot reset avatar: BoneMap missing."
            );

            return;
        }

        // Stop the current pose from being applied.
        currentPose = null;

        // Reset all tracked bones to their
        // original Mixamo rotations.
        if (boneMap.spine != null)
            boneMap.spine.rotation =
                initialSpineRotation;

        if (boneMap.leftUpperArm != null)
            boneMap.leftUpperArm.rotation =
                initialLeftUpperArmRotation;

        if (boneMap.leftForeArm != null)
            boneMap.leftForeArm.rotation =
                initialLeftForeArmRotation;

        if (boneMap.rightUpperArm != null)
            boneMap.rightUpperArm.rotation =
                initialRightUpperArmRotation;

        if (boneMap.rightForeArm != null)
            boneMap.rightForeArm.rotation =
                initialRightForeArmRotation;

        if (boneMap.leftUpperLeg != null)
            boneMap.leftUpperLeg.rotation =
                initialLeftUpperLegRotation;

        if (boneMap.leftLowerLeg != null)
            boneMap.leftLowerLeg.rotation =
                initialLeftLowerLegRotation;

        if (boneMap.rightUpperLeg != null)
            boneMap.rightUpperLeg.rotation =
                initialRightUpperLegRotation;

        if (boneMap.rightLowerLeg != null)
            boneMap.rightLowerLeg.rotation =
                initialRightLowerLegRotation;

        // Reset tracking state.
        calibrated = false;

        bodyInvalidFrames = 0;

        leftArmInvalidFrames = 0;
        rightArmInvalidFrames = 0;

        leftLegInvalidFrames = 0;
        rightLegInvalidFrames = 0;

        bodyTrackingAvailable = false;

        if (poseCalibrator != null)
            poseCalibrator.Reset();

        Debug.Log(
            "[AvatarTracking] " +
            "Avatar reset to Mixamo rest pose."
        );
    }

    // =========================================================
    // BONE DIRECTION
    // =========================================================

    private Vector3 GetBoneDirection(
        Transform bone,
        Transform child)
    {
        if (bone == null ||
            child == null)
        {
            return Vector3.zero;
        }

        Vector3 direction =
            child.position -
            bone.position;

        if (direction.sqrMagnitude <
            0.000001f)
        {
            return Vector3.zero;
        }

        return direction.normalized;
    }

    // =========================================================
    // ARMS
    // =========================================================

    private void UpdateArms()
    {
        UpdateLeftArm();
        UpdateRightArm();
    }

    // =========================================================
    // LEFT ARM
    // =========================================================

    private void UpdateLeftArm()
    {
        PoseLandmark shoulder = null;
        PoseLandmark elbow = null;
        PoseLandmark wrist = null;

        bool valid =
            TryGetUsable(
                "LEFT_SHOULDER",
                out shoulder
            ) &&
            TryGetUsable(
                "LEFT_ELBOW",
                out elbow
            ) &&
            TryGetUsable(
                "LEFT_WRIST",
                out wrist
            );

        if (!valid)
        {
            leftArmInvalidFrames++;
            return;
        }

        Vector3 upperDirection =
            poseProcessor.GetDirection(
                shoulder,
                elbow,
                useWorldCoordinates
            );

        Vector3 foreDirection =
            poseProcessor.GetDirection(
                elbow,
                wrist,
                useWorldCoordinates
            );

        if (upperDirection == Vector3.zero ||
            foreDirection == Vector3.zero)
        {
            leftArmInvalidFrames++;
            return;
        }

        leftArmInvalidFrames = 0;

        ApplyRestRotation(
            boneMap.leftUpperArm,
            initialLeftUpperArmRotation,
            initialLeftUpperArmDirection,
            upperDirection
        );

        ApplyRestRotation(
            boneMap.leftForeArm,
            initialLeftForeArmRotation,
            initialLeftForeArmDirection,
            foreDirection
        );
    }

    // =========================================================
    // RIGHT ARM
    // =========================================================

    private void UpdateRightArm()
    {
        PoseLandmark shoulder = null;
        PoseLandmark elbow = null;
        PoseLandmark wrist = null;

        bool valid =
            TryGetUsable(
                "RIGHT_SHOULDER",
                out shoulder
            ) &&
            TryGetUsable(
                "RIGHT_ELBOW",
                out elbow
            ) &&
            TryGetUsable(
                "RIGHT_WRIST",
                out wrist
            );

        if (!valid)
        {
            rightArmInvalidFrames++;
            return;
        }

        Vector3 upperDirection =
            poseProcessor.GetDirection(
                shoulder,
                elbow,
                useWorldCoordinates
            );

        Vector3 foreDirection =
            poseProcessor.GetDirection(
                elbow,
                wrist,
                useWorldCoordinates
            );

        if (upperDirection == Vector3.zero ||
            foreDirection == Vector3.zero)
        {
            rightArmInvalidFrames++;
            return;
        }

        rightArmInvalidFrames = 0;

        ApplyRestRotation(
            boneMap.rightUpperArm,
            initialRightUpperArmRotation,
            initialRightUpperArmDirection,
            upperDirection
        );

        ApplyRestRotation(
            boneMap.rightForeArm,
            initialRightForeArmRotation,
            initialRightForeArmDirection,
            foreDirection
        );
    }

    // =========================================================
    // SPINE
    // =========================================================

    private void UpdateSpine()
    {
        PoseLandmark leftShoulder = null;
        PoseLandmark rightShoulder = null;
        PoseLandmark leftHip = null;
        PoseLandmark rightHip = null;

        bool valid =
            TryGetUsable(
                "LEFT_SHOULDER",
                out leftShoulder
            ) &&
            TryGetUsable(
                "RIGHT_SHOULDER",
                out rightShoulder
            ) &&
            TryGetUsable(
                "LEFT_HIP",
                out leftHip
            ) &&
            TryGetUsable(
                "RIGHT_HIP",
                out rightHip
            );

        if (!valid)
        {
            return;
        }

        Vector3 shoulderCenter =
            poseProcessor.GetMidpoint(
                leftShoulder,
                rightShoulder,
                useWorldCoordinates
            );

        Vector3 hipCenter =
            poseProcessor.GetMidpoint(
                leftHip,
                rightHip,
                useWorldCoordinates
            );

        Vector3 torsoDirection =
            shoulderCenter -
            hipCenter;

        if (torsoDirection.sqrMagnitude <
            0.000001f)
        {
            return;
        }

        torsoDirection.Normalize();

        ApplyRestRotation(
            boneMap.spine,
            initialSpineRotation,
            initialSpineDirection,
            torsoDirection
        );
    }

    // =========================================================
    // LEGS
    // =========================================================

    private void UpdateLegs()
    {
        UpdateLeftLeg();
        UpdateRightLeg();
    }

    // =========================================================
    // LEFT LEG
    // =========================================================

    private void UpdateLeftLeg()
    {
        PoseLandmark hip = null;
        PoseLandmark knee = null;
        PoseLandmark ankle = null;

        bool valid =
            TryGetUsable(
                "LEFT_HIP",
                out hip
            ) &&
            TryGetUsable(
                "LEFT_KNEE",
                out knee
            ) &&
            TryGetUsable(
                "LEFT_ANKLE",
                out ankle
            );

        if (!valid)
        {
            leftLegInvalidFrames++;
            return;
        }

        Vector3 upperDirection =
            poseProcessor.GetDirection(
                hip,
                knee,
                useWorldCoordinates
            );

        Vector3 lowerDirection =
            poseProcessor.GetDirection(
                knee,
                ankle,
                useWorldCoordinates
            );

        if (upperDirection == Vector3.zero ||
            lowerDirection == Vector3.zero)
        {
            leftLegInvalidFrames++;
            return;
        }

        leftLegInvalidFrames = 0;

        ApplyRestRotation(
            boneMap.leftUpperLeg,
            initialLeftUpperLegRotation,
            initialLeftUpperLegDirection,
            upperDirection
        );

        ApplyRestRotation(
            boneMap.leftLowerLeg,
            initialLeftLowerLegRotation,
            initialLeftLowerLegDirection,
            lowerDirection
        );
    }

    // =========================================================
    // RIGHT LEG
    // =========================================================

    private void UpdateRightLeg()
    {
        PoseLandmark hip = null;
        PoseLandmark knee = null;
        PoseLandmark ankle = null;

        bool valid =
            TryGetUsable(
                "RIGHT_HIP",
                out hip
            ) &&
            TryGetUsable(
                "RIGHT_KNEE",
                out knee
            ) &&
            TryGetUsable(
                "RIGHT_ANKLE",
                out ankle
            );

        if (!valid)
        {
            rightLegInvalidFrames++;
            return;
        }

        Vector3 upperDirection =
            poseProcessor.GetDirection(
                hip,
                knee,
                useWorldCoordinates
            );

        Vector3 lowerDirection =
            poseProcessor.GetDirection(
                knee,
                ankle,
                useWorldCoordinates
            );

        if (upperDirection == Vector3.zero ||
            lowerDirection == Vector3.zero)
        {
            rightLegInvalidFrames++;
            return;
        }

        rightLegInvalidFrames = 0;

        ApplyRestRotation(
            boneMap.rightUpperLeg,
            initialRightUpperLegRotation,
            initialRightUpperLegDirection,
            upperDirection
        );

        ApplyRestRotation(
            boneMap.rightLowerLeg,
            initialRightLowerLegRotation,
            initialRightLowerLegDirection,
            lowerDirection
        );
    }

    // =========================================================
    // REST-POSE ROTATION
    // =========================================================

    private void ApplyRestRotation(
        Transform bone,
        Quaternion initialRotation,
        Vector3 initialDirection,
        Vector3 targetDirection)
    {
        if (bone == null)
            return;

        if (initialDirection == Vector3.zero)
            return;

        if (targetDirection == Vector3.zero)
            return;

        Quaternion delta =
            Quaternion.FromToRotation(
                initialDirection,
                targetDirection
            );

        Quaternion targetRotation =
            delta *
            initialRotation;

        bone.rotation =
            Quaternion.Slerp(
                bone.rotation,
                targetRotation,
                rotationSmoothness
            );
    }

    // =========================================================
    // LANDMARK ACCESS
    // =========================================================

    private bool TryGetUsable(
        string landmarkName,
        out PoseLandmark landmark)
    {
        landmark = null;

        if (currentPose == null)
            return false;

        if (!currentPose.TryGetLandmark(
            landmarkName,
            out landmark))
        {
            return false;
        }

        if (landmark == null)
            return false;

        return landmark.visibility >=
               minimumVisibility;
    }

    private bool HasUsable(
        string landmarkName)
    {
        PoseLandmark landmark;

        return TryGetUsable(
            landmarkName,
            out landmark
        );
    }

    // =========================================================
    // TRACKING STATUS
    // =========================================================

    public string GetTrackingStatus()
    {
        if (!calibrated)
            return "CALIBRATING";

        if (!bodyTrackingAvailable)
            return "LOST";

        bool armsLimited =
            leftArmInvalidFrames >
            maximumHeldFrames ||
            rightArmInvalidFrames >
            maximumHeldFrames;

        bool legsLimited =
            leftLegInvalidFrames >
            maximumHeldFrames ||
            rightLegInvalidFrames >
            maximumHeldFrames;

        if (armsLimited || legsLimited)
            return "LIMITED";

        return "GOOD";
    }

    // =========================================================
    // DEBUG
    // =========================================================

    private void DebugMessage(
        string message)
    {
        if (!enableDebugLogs)
            return;

        if (debugFrameCounter <
            debugIntervalFrames)
        {
            return;
        }

        debugFrameCounter = 0;

        Debug.Log(
            "[AvatarTracking] " +
            message
        );
    }

    // =========================================================
    // RECALIBRATION
    // =========================================================

    public void Recalibrate()
    {
        poseCalibrator.Reset();

        calibrated = false;

        bodyInvalidFrames = 0;

        leftArmInvalidFrames = 0;
        rightArmInvalidFrames = 0;

        leftLegInvalidFrames = 0;
        rightLegInvalidFrames = 0;

        bodyTrackingAvailable = false;

        Debug.Log(
            "[AvatarTracking] " +
            "Calibration reset. " +
            "Waiting for stable pose."
        );
    }

    public bool IsCalibrated()
    {
        return calibrated;
    }

    public string GetCalibrationState()
    {
        if (poseCalibrator == null)
            return "UNINITIALIZED";

        return poseCalibrator.State.ToString();
    }

    public int GetStableFrameCount()
    {
        if (poseCalibrator == null)
            return 0;

        return poseCalibrator.StableFrameCount;
    }
}