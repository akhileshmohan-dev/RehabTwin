using System;

[Serializable]
public class PoseLandmark
{
    // Landmark name
    public string name;

    // ---------------------------------------------------------
    // Image-space coordinates
    // ---------------------------------------------------------

    public float x;
    public float y;
    public float z;

    // Visibility
    public float visibility;

    // ---------------------------------------------------------
    // MediaPipe World coordinates
    // ---------------------------------------------------------

    public float world_x;
    public float world_y;
    public float world_z;
}