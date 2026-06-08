using System.Collections;
using System.IO;
using System.Collections.Generic;
using UnityEngine;

public class DataLogger : MonoBehaviour
{
    private string path;

    private void Start()
    {
        path = Application.dataPath + "/dataLog.txt";

        // If the file doesn't exist, create it.
        if (!File.Exists(path))
        {
            Debug.Log("Creating file at " + path);
            File.WriteAllText(path, "Data Log for \"Drone design challenge\"\n\n");
        }
    }

    public void LogData(string dataToLog)
    {
        // Add new data to the existing file.
        File.AppendAllText(path, dataToLog + "\n");
    }
}
