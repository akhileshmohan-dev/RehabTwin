using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class PoseReceiver : MonoBehaviour
{
    [Header("Network")]
    public int port = 5005;

    private UdpClient udpClient;
    private IPEndPoint endPoint;

    // The latest pose received from Python
    // or supplied by the replay system.
    public PoseFrame LatestPose { get; private set; }

    void Start()
    {
        try
        {
            udpClient = new UdpClient(port);
            endPoint = new IPEndPoint(
                IPAddress.Any,
                port
            );

            Debug.Log(
                "RehabTwin: UDP receiver started on port " + port
            );
        }
        catch (Exception e)
        {
            Debug.LogError(
                "RehabTwin: Could not start UDP receiver.\n" +
                e.Message
            );

            return;
        }
    }

    void Update()
    {
        ReceivePose();
    }

    // =========================================================
    // LIVE POSE RECEPTION
    // =========================================================

    void ReceivePose()
    {
        if (udpClient == null)
            return;

        try
        {
            while (udpClient.Available > 0)
            {
                byte[] data =
                    udpClient.Receive(ref endPoint);

                string json =
                    Encoding.UTF8.GetString(data);

                PoseFrame pose =
                    JsonUtility.FromJson<PoseFrame>(json);

                if (pose == null ||
                    pose.landmarks == null)
                {
                    continue;
                }

                pose.BuildLookup();

                LatestPose = pose;
            }
        }
        catch (Exception e)
        {
            Debug.LogError(
                "RehabTwin: UDP receive error.\n" +
                e.Message
            );
        }
    }

    // =========================================================
    // REPLAY SUPPORT
    // =========================================================

    /// <summary>
    /// Supplies a recorded pose to the system.
    ///
    /// ReplayController will use this method to inject
    /// frame-by-frame poses from an old session log.
    /// </summary>
    public void SetReplayPose(PoseFrame pose)
    {
        if (pose == null)
            return;

        pose.BuildLookup();

        LatestPose = pose;
    }

    // =========================================================
    // LANDMARK ACCESS
    // =========================================================

    public bool TryGetLandmark(
        string landmarkName,
        out PoseLandmark landmark)
    {
        landmark = null;

        if (LatestPose == null)
            return false;

        return LatestPose.TryGetLandmark(
            landmarkName,
            out landmark
        );
    }

    // =========================================================
    // CLEANUP
    // =========================================================

    void OnDestroy()
    {
        if (udpClient != null)
        {
            udpClient.Close();
            udpClient = null;
        }
    }
}