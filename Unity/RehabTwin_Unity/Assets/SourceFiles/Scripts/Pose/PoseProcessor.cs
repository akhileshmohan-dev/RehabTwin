using UnityEngine;

public class PoseProcessor
{
    public bool mirrorX = true;

    public float smoothing = 0.35f;

    public PoseFrame Process(PoseFrame rawPose)
    {
        if (rawPose == null || rawPose.landmarks == null)
            return null;

        rawPose.BuildLookup();

        PoseFrame processedPose = new PoseFrame();

        processedPose.landmarks =
            new PoseLandmark[rawPose.landmarks.Length];

        for (int i = 0; i < rawPose.landmarks.Length; i++)
        {
            PoseLandmark source =
                rawPose.landmarks[i];

            if (source == null)
                continue;

            PoseLandmark processed =
                new PoseLandmark();

            processed.name =
                source.name;

            processed.x =
                source.x;

            processed.y =
                source.y;

            processed.z =
                source.z;

            processed.visibility =
                source.visibility;

            // --------------------------------------------------
            // KEEP MEDIAPIPE WORLD COORDINATES RAW
            // --------------------------------------------------

            processed.world_x =
                source.world_x;

            processed.world_y =
                source.world_y;

            processed.world_z =
                source.world_z;

            /*
             * IMPORTANT:
             *
             * Do NOT mirror the world coordinates here.
             *
             * Left/right identity is already represented by
             * the landmark names.
             *
             * We will handle coordinate conversion centrally
             * when converting the pose into Unity space.
             */

            processedPose.landmarks[i] =
                processed;
        }

        processedPose.BuildLookup();

        return processedPose;
    }

    // =========================================================
    // MEDIAPIPE WORLD → UNITY
    // =========================================================

    public Vector3 GetPosition(
        PoseLandmark landmark,
        bool useWorldCoordinates = true)
    {
        if (landmark == null)
            return Vector3.zero;

        if (useWorldCoordinates)
        {
            /*
             * MediaPipe:
             *
             * X = horizontal
             * Y = down
             * Z = depth
             *
             * Unity:
             *
             * X = horizontal
             * Y = up
             * Z = depth
             *
             * Therefore Y must be inverted.
             */

            float x =
                landmark.world_x;

            float y =
                -landmark.world_y;

            float z =
                -landmark.world_z;

            if (mirrorX)
                x = -x;

            return new Vector3(
                x,
                y,
                z
            );
        }

        // -----------------------------------------------------
        // IMAGE COORDINATES
        // -----------------------------------------------------

        float imageX =
            landmark.x / 1000f;

        float imageY =
            -landmark.y / 1000f;

        float imageZ =
            -landmark.z;

        if (mirrorX)
            imageX = -imageX;

        return new Vector3(
            imageX,
            imageY,
            imageZ
        );
    }

    // =========================================================
    // MIDPOINT
    // =========================================================

    public Vector3 GetMidpoint(
        PoseLandmark first,
        PoseLandmark second,
        bool useWorldCoordinates = true)
    {
        if (first == null || second == null)
            return Vector3.zero;

        Vector3 a =
            GetPosition(
                first,
                useWorldCoordinates
            );

        Vector3 b =
            GetPosition(
                second,
                useWorldCoordinates
            );

        return (a + b) * 0.5f;
    }

    // =========================================================
    // DIRECTION
    // =========================================================

    public Vector3 GetDirection(
        PoseLandmark from,
        PoseLandmark to,
        bool useWorldCoordinates = true)
    {
        if (from == null || to == null)
            return Vector3.zero;

        Vector3 start =
            GetPosition(
                from,
                useWorldCoordinates
            );

        Vector3 end =
            GetPosition(
                to,
                useWorldCoordinates
            );

        Vector3 direction =
            end - start;

        if (direction.sqrMagnitude < 0.000001f)
            return Vector3.zero;

        return direction.normalized;
    }

    // =========================================================
    // DISTANCE
    // =========================================================

    public float GetDistance(
        PoseLandmark first,
        PoseLandmark second,
        bool useWorldCoordinates = true)
    {
        if (first == null || second == null)
            return 0f;

        Vector3 a =
            GetPosition(
                first,
                useWorldCoordinates
            );

        Vector3 b =
            GetPosition(
                second,
                useWorldCoordinates
            );

        return Vector3.Distance(
            a,
            b
        );
    }
}