using UnityEngine;
using UnityEditor;
using System.IO;
using System.Text;

public class ExportHierarchy
{
    [MenuItem("RehabTwin/Export Character Hierarchy")]
    public static void Export()
    {
        GameObject character =
            GameObject.Find("Character_Model");

        if (character == null)
        {
            Debug.LogError(
                "RehabTwin: Character_Model not found!"
            );
            return;
        }

        StringBuilder output =
            new StringBuilder();

        output.AppendLine(
            "RehabTwin Character Hierarchy"
        );

        output.AppendLine(
            "================================"
        );

        WriteHierarchy(
            character.transform,
            output,
            0
        );

        string path =
            Path.Combine(
                Application.dataPath,
                "../Character_Hierarchy.txt"
            );

        File.WriteAllText(
            path,
            output.ToString()
        );

        Debug.Log(
            "RehabTwin: Character hierarchy exported to:\n" +
            path
        );

        EditorUtility.RevealInFinder(path);
    }

    static void WriteHierarchy(
        Transform current,
        StringBuilder output,
        int depth)
    {
        output.AppendLine(
            new string(' ', depth * 4) +
            "└── " +
            current.name
        );

        foreach (Transform child in current)
        {
            WriteHierarchy(
                child,
                output,
                depth + 1
            );
        }
    }
}