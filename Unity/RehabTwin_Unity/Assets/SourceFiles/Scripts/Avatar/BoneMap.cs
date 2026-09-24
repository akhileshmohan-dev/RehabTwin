using UnityEngine;

public class BoneMap : MonoBehaviour
{
    [Header("Root / Lower Body")]
    public Transform hips;
    public Transform spine;
    public Transform spine1;
    public Transform spine2;

    [Header("Left Arm")]
    public Transform leftShoulder;
    public Transform leftUpperArm;
    public Transform leftForeArm;
    public Transform leftHand;

    [Header("Right Arm")]
    public Transform rightShoulder;
    public Transform rightUpperArm;
    public Transform rightForeArm;
    public Transform rightHand;

    [Header("Left Leg")]
    public Transform leftUpperLeg;
    public Transform leftLowerLeg;
    public Transform leftFoot;

    [Header("Right Leg")]
    public Transform rightUpperLeg;
    public Transform rightLowerLeg;
    public Transform rightFoot;

    public bool IsValid()
    {
        return
            hips != null &&
            spine != null &&
            spine1 != null &&
            spine2 != null &&

            leftShoulder != null &&
            leftUpperArm != null &&
            leftForeArm != null &&

            rightShoulder != null &&
            rightUpperArm != null &&
            rightForeArm != null &&

            leftUpperLeg != null &&
            leftLowerLeg != null &&

            rightUpperLeg != null &&
            rightLowerLeg != null;
    }
}