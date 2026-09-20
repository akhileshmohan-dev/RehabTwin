using System;
using System.Collections.Generic;

[Serializable]
public class PoseFrame
{
    public PoseLandmark[] landmarks;

    private Dictionary<string, PoseLandmark> lookup;

    public void BuildLookup()
    {
        lookup = new Dictionary<string, PoseLandmark>();

        if (landmarks == null)
            return;

        foreach (PoseLandmark landmark in landmarks)
        {
            if (landmark == null || string.IsNullOrEmpty(landmark.name))
                continue;

            lookup[landmark.name] = landmark;
        }
    }

    public bool TryGetLandmark(
        string landmarkName,
        out PoseLandmark landmark)
    {
        landmark = null;

        if (lookup == null)
            BuildLookup();

        return lookup.TryGetValue(
            landmarkName,
            out landmark
        );
    }
}