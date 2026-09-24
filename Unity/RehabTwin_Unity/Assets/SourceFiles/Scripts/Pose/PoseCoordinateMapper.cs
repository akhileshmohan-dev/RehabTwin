using UnityEngine;

public class PoseCoordinateMapper
{
    public static Vector3 WorldToUnity(PoseLandmark landmark)
    {
        if (landmark == null)
            return Vector3.zero;

        /*
         * MediaPipe World coordinates:
         *
         * X → left / right
         * Y → up / down
         * Z → depth
         *
         * Unity:
         *
         * X → left / right
         * Y → up / down
         * Z → forward
         */

        float x = landmark.world_x;
        float y = landmark.world_y;

        // Correct depth direction for the avatar.
        float z = landmark.world_z;

        return new Vector3(
            x,
            y,
            z
        );
    }

    public static Vector3 ImageToUnity(
        PoseLandmark landmark,
        bool mirrorX = true)
    {
        if (landmark == null)
            return Vector3.zero;

        float x =
            landmark.x / 1000f;

        float y =
            -landmark.y / 1000f;

        float z =
            -landmark.z;

        if (mirrorX)
        {
            x = -x;
        }

        return new Vector3(
            x,
            y,
            z
        );
    }
}