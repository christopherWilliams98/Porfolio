using UnityEngine;
using System.IO;

public class LogParser : MonoBehaviour
{
    private DataLogger dataLogger; // Reference to the DataLogger script

    private void Start()
    {
        // Find the GameObject with the DataLogger script
        dataLogger = FindObjectOfType<DataLogger>();

        if (dataLogger == null)
        {
            Debug.LogError("DataLogger not found in the scene.");
            return;
        }

        // Read the dataLog.txt file and call a function to parse and generate CSV
        string logFilePath = Application.dataPath + "/dataLog.txt";
        if (File.Exists(logFilePath))
        {
            string textData = File.ReadAllText(logFilePath);
            ParseAndGenerateCSV(textData);
        }
        else
        {
            Debug.LogError("dataLog.txt file not found.");
        }
    }

    private void ParseAndGenerateCSV(string textData)
    {
        LogToCSV logToCSV = new LogToCSV();
        logToCSV.ParseLogData(textData);
        logToCSV.GenerateCSV(Application.dataPath + "/game_data.csv");
    }
}
