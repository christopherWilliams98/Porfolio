using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

public class LogToCSV
{
    public struct LogEntry
    {
        public string Type;
        public string Location;
        public string Choice;
        public string TimeSpent;
        public string Date;
    }

    public List<LogEntry> LogEntries { get; private set; } = new List<LogEntry>();
    public void ParseLogData(string textData)
{
    // Clear existing log entries
    LogEntries.Clear();

    string[] lines = textData.Split('\n');

    LogEntry currentEntry = new LogEntry();

    foreach (string line in lines)
    {
        if (line.Contains("Log for game session started at time:"))
        {
            // Extract date
            Match dateMatch = Regex.Match(line, @"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}");
            if (dateMatch.Success)
            {
                currentEntry.Date = dateMatch.Value;
            }
        }
        else if (line.Contains("Location:") && !line.Contains("left"))
        {
            // Extract location
            currentEntry.Type = "Location Entry";
            currentEntry.Location = line.Split(':')[1].Trim();
        }
        else if (line.Contains("Choice:"))
        {
            // Extract choice and time spent
            Match choiceMatch = Regex.Match(line, "Choice:(.*) was accepted at time:");
            if (choiceMatch.Success)
            {
                currentEntry.Type = "Choice Accepted";
                currentEntry.Choice = choiceMatch.Groups[1].Value.Trim();
            }
            else
            {
                currentEntry.Type = "Choice Made";
                currentEntry.Choice = line.Split(':')[1].Trim();
            }
            
            Match timeSpentMatch = Regex.Match(line, @"\d+\.\d+\s+seconds");
            if (timeSpentMatch.Success)
            {
                currentEntry.TimeSpent = timeSpentMatch.Value.Replace(" seconds", "");
            }
        }
        else if (line.Contains("End of game"))
        {
            // Add the current entry to the list
            LogEntries.Add(currentEntry);

            // Reset the current entry
            currentEntry = new LogEntry();
        }
    }
}



    public void GenerateCSV(string filePath)
    {
        // Clear the existing CSV file
        File.WriteAllText(filePath, string.Empty);

        using (StreamWriter writer = new StreamWriter(filePath))
        {
            writer.WriteLine("Type,Location,Choice,Time Spent (seconds),Date");
            foreach (LogEntry entry in LogEntries)
            {
                writer.WriteLine($"{entry.Type},{entry.Location},{entry.Choice},{entry.TimeSpent},{entry.Date}");
            }
        }
    }
}