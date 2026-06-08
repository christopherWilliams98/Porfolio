using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using System.Text;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using System;
using System.Timers;
using UnityEngine.PlayerLoop;
using System.Linq;

// List of possible locations to visit
public enum choices
{
    None, //0
	DroneExpert, //1
    BirdExpert, //expert on specific bird (choice2)
    TestLocally, //test in backyard (choice id: 3)
    //OnSiteVisit, //nothern ireland lots of rain and WIND! in winter for example
    OnFieldTesting, //choice id: 4
    userTesting, //choice id: 5
    resevoirDirector, //choice id: 6
    shipIt, //choice id: 7
    Tutorial, //choice id: 8
}

public class CelluloGameController : MonoBehaviour
{
    public DataLogger dataLogger;
    private Color orange = new Color(254/255f, 97/255f, 0/255f, 1f);
    //Drone Specs
    private static int protoNoiseLevel = 80; // [db]
    private static int protoDroneSize = 25;
    private static double protoDroneWeight = 1.0;
    private static string protoDroneColor = "Blue";
    private static string protoFrameMaterial = "Aluminium";
    private static int protoDroneLifespan = 10;
    private static string protoPropellerMaterial = "Plastic";
    private static bool has_wetsuit = false;
    private static bool has_manual = false;
    private static bool has_foldable_propellers = false;    
    private static bool once = true;
    private static int lastProtoNoiseLevel = 80;
    private static int lastProtoDroneSize = 25;
    private static double lastProtoDroneWeight = 1.0;
    private static string lastProtoDroneColor = "Blue";
    private static string lastProtoFrameMaterial = "Aluminium";
    private static int lastProtoDroneLifespan = 10;
    private static string lastProtoPropellerMaterial = "Plastic";
    private static bool lastHas_wetsuit = false;
    private static bool lastHas_manual = false;
    private static bool lastHas_foldable_propellers = false;
    private Dictionary<string, bool> changedSpecs = new Dictionary<string, bool>();
    public TextMeshProUGUI droneSpecsText;
    public Image droneImage;
    public Sprite droneWhiteSpriteImage;
    public Sprite dronePurpleSpriteImage;
    public MainCelluloController celluloController;
    //Main dialogue text
    public DialogueTrigger EnterButton;
    public TextMeshProUGUI dialogueTextBox;
    public List<(String subChoiceNumber, double? timeSpent)> sortedTimeSpentList = new List<(String subChoiceNumber, double? timeSpent)>();

    //Audio
    public List<string> ansleyAudio = new List<string>();
    public List<string> davinaAudio = new List<string>();
    public List<string> fionaAudio = new List<string>();
    
    //Array of locked choice and choice selection objects
    List<int> locked_choices = new List<int>(); //List of choices locked in by the players

    /* Array of dialogues -------------------------------------------------------*/
    [SerializeField] private List<Dialogue> choiceFeedbackDialogues;//set in unity directly
    private string[] finalOutcomeDialogueSentences = {"var 0", "var 1", 
    "var 2", "var 3", "var4"};

    /*ACCEPT/REFUSE------------------------------------------------------------------*/
    public int latestChoiceId = 0;
    int acceptedSubChoiceNumber = 0; //represents the current subchoice withing the main choice

    /*Money and Time System ---------------------------------------------------------------*/
    public TextMeshProUGUI availableBalanceText;
    public TextMeshProUGUI remainingTimeText;
    static public float remainingTime = 11f; //number of weeks remaning till project deadline 
    static public int availableBalance = 300; //Starting budget
    public int[] mainChoiceFinancialCosts; //Costs of each main choice, set in unity
    public float[] mainChoiceTimeCosts; //timeCosts of each main choice, set in unity
    // -----------------------------------------------------------------------------
    void Start()
    {
        Screen.SetResolution(1920, 1080, false); // false indicates windowed mode

        //Print balance and drone specs 
        if(SceneManager.GetActiveScene().name == "DroneGameCellulo") {
            remainingTimeText.text = "Time Left: \n" +  remainingTime.ToString("F1") +" Weeks"; 
            availableBalanceText.text = "Balance: " + availableBalance.ToString() +" CHF"; 
        }

        dataLogger = GetComponent<DataLogger>();

        if(dataLogger == null)
        {
            Debug.LogError("DataLogger reference not set in ChoiceSelection.");
            return;
        }

        refreshDroneSpecs();
        PlayConfirmationSound();
    }

    public void LogDataViaController(string dataToLog)
    {
        if (dataLogger != null)
        {
            dataLogger.LogData(dataToLog);
        }
        else
        {
            Debug.LogError("DataLogger not found on this GameObject.");
        }
    }


    /**
    Enables/disables the dialogue box
    */
    public void enableDialogueBox(bool enable){
        if(enable){
            dialogueTextBox.gameObject.SetActive(true);
            dialogueTextBox.gameObject.transform.parent.gameObject.SetActive(true);
        }else{
            dialogueTextBox.gameObject.SetActive(false);
            dialogueTextBox.gameObject.transform.parent.gameObject.SetActive(false);
        }
    }

    
    Dictionary<string, int> locations = new Dictionary<string, int>(){
        {"None", 0},
        {"TechShop", 1},
        {"Ornithologist", 2},
        {"CityPark", 3},
        {"ExternalLocation", 4},
        {"CityHall", 5},
        {"BirdReservoir", 6},
        {"PostOffice", 7},
        {"TutorialClassroom", 8},
        {"TutorialBus", 9}
    };
    
    private int findChoiceId(){
        GameObject allMaps = GameObject.Find("HouseMaps");
        foreach(Transform child in allMaps.transform){
            if(child.gameObject.activeSelf)
            {
                return locations[child.gameObject.name];
            }
        }
        return 0;
    }

    /**
    Manages what happens any time a user locks in a choice.
    This is triggered any time a user locks in a choice by placing their cellulo 
    on a doorway or choice pad and interacting with it. 
    */
    public void lockInChoice() {
        acceptedSubChoiceNumber = 0; //reset subChoice index

        latestChoiceId = findChoiceId(); // get the current choice from all locations

        //Get cost of choice and check if have avaible funds
        float mainChoiceTimeCost = mainChoiceTimeCosts[latestChoiceId];
        int mainChoiceFinancialCost = mainChoiceFinancialCosts[latestChoiceId];

        //If sufficient resources
        if(checkIfEnoughResources(mainChoiceTimeCost, mainChoiceFinancialCost)){
            
            locked_choices.Add(latestChoiceId); // Add to List of locked choices TODO CAN REMOVE THIS PROBABLY LATER
        
            //Update game paramaters and UI
            updateMainTabText(choiceFeedbackDialogues[latestChoiceId]); //update text in main tab

            EnterButton.TriggerDialogueMainTab(); //trigger dialogue 

            //update available time and balance due to locking in this main choice
            updateAvailableBalanceAndTimeForMainChoice(latestChoiceId);
        } else {
            GameObject.Find("ReturnPad").GetComponent<Interactable_Point>().Interact();
        }

    }

    /**
    Called by DialogueManager when subChoice is accepted or refused
    */
    public void incrementSubChoiceNum() {
        acceptedSubChoiceNumber++;
    }

    /**
    /// Input: cost of currently selected subchoice
    /// Output: Boolean indicating if have enough resources
    **/
    public bool checkIfEnoughResources(float timeCost, int financialCost){
        //if not enough resources return false
        if(availableBalance < financialCost || remainingTime < timeCost){
            return false;
        }
        return true;
    }
    /**
    This method is called whenever a choice is made
    Updates drone ranges according to accepted subChoice
    */
    public void updateDroneRangesAndResources(int acceptedSubChoiceNumber){
        //Once we know what choice was made, need to check if have enough funds before executing changes.
        float timeCost= (float)0.0;
        int financialCost = 0;
        bool isSuccessful = false;
        string choiceId = "Invalid";
        //celluloController = GameObject.FindGameObjectWithTag("Player").gameObject.GetComponent<MainCelluloController>();
        if(latestChoiceId == (int)choices.DroneExpert){
            if(acceptedSubChoiceNumber == 0){ //repait drone white
                timeCost= (float)0.5;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    protoDroneColor = "White";
                    isSuccessful = true;
                    choiceId = " Drone Expert - Repaint drone white";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
                
            }
            if(acceptedSubChoiceNumber == 1){ //create manual
                timeCost =(float)2.0;
                financialCost = 0;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    has_manual = true;
                    isSuccessful = true;
                    choiceId = " Drone Expert - Create manual";
                } else {
                    notEnoughResources(celluloController);
                    return;
                } 
            }
        }
        if(latestChoiceId == (int)choices.BirdExpert){
            //Bird expert ultimately suggest not to make it white
            if(acceptedSubChoiceNumber == 0) { //Repaint drone purple
                timeCost = (float)0.5;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    protoDroneColor = "Purple";
                    isSuccessful = true;
                    choiceId = " Ornithologist - Repaint drone purple";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 1) { //Make drone out of carbon fiber
                timeCost = (float)0.5;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    protoPropellerMaterial = "Carbon Fiber";
                    protoNoiseLevel -= 10;
                    isSuccessful = true;
                    choiceId = " Ornithologist - Change propeller material to Carbon Fiber";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            }
        }
        if(latestChoiceId == (int)choices.TestLocally){
            if(acceptedSubChoiceNumber == 0) { // Make bigger for bigger battery
                timeCost = (float)2.0;
                financialCost = 100;
                if(checkIfEnoughResources(timeCost,financialCost)){
                    protoDroneWeight += 0.5;
                    protoDroneSize += 10;
                    protoNoiseLevel += 10;
                    protoDroneLifespan += 5;
                    isSuccessful = true;
                    choiceId = " City Park - Bigger battery";
                } else
                {
                    notEnoughResources(celluloController);
                    return;
                }
            }
        }
        if(latestChoiceId == (int)choices.OnFieldTesting){
            if(acceptedSubChoiceNumber == 0) { //wetsuit
                timeCost = (float)2.0;
                financialCost = 100;
                if(checkIfEnoughResources(timeCost,financialCost)){
                    has_wetsuit = true;
                    isSuccessful = true;
                    choiceId = " External Location - Add wetsuit";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 1) { //get bigger battery
                timeCost = (float)1.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost,financialCost)){
                    protoDroneWeight += 0.5;
                    protoDroneSize += 10;
                    protoNoiseLevel += 10;
                    protoDroneLifespan += 3;
                    isSuccessful = true;
                    choiceId = " External Location - Bigger battery";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 2) { //switch to Carbon Fiber
                timeCost = (float)1.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost,financialCost)){
                    //If switching from a heavier material, battery lifespan increases
                    if(protoFrameMaterial == "Wood" || protoFrameMaterial == "Aluminium") {
                        protoDroneWeight -= 0.5;
                        protoNoiseLevel -= 10;
                        protoDroneLifespan += 5;
                        isSuccessful = true;
                        choiceId = " External Location - Change frame material to Carbon Fiber";
                    }
                    protoFrameMaterial = "Carbon Fiber";
                    
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            }
        }

        if(latestChoiceId == (int)choices.userTesting){
            if(acceptedSubChoiceNumber == 0) { //Foldable propellers
                timeCost = (float)0.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    has_foldable_propellers = true;
                    isSuccessful = true;
                    choiceId = " Town Council - Add foldable propellers";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 1) { // Make drone lighter
                timeCost = (float)1.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost,financialCost)){
                    protoDroneWeight -= 0.25;
                    protoNoiseLevel -= 5;
                    protoDroneLifespan += 2;
                    isSuccessful = true;
                    choiceId = " Town Council - Make drone lighter";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            }
        }

        if(latestChoiceId == (int)choices.resevoirDirector){
            if(acceptedSubChoiceNumber == 0) { //take director insight and use wood propeller
                timeCost = (float)0.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    if(protoPropellerMaterial == "Plastic") {
                        protoNoiseLevel -= 10;
                        isSuccessful = true;
                        choiceId = " Bird Reservoir - Change propeller material to Wood";
                    }
                    protoPropellerMaterial = "Wood";
                    
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 1) { //switch to carbon fiber if not already?(reapeat same pro&cons as last time)
                timeCost = (float) 1.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    protoFrameMaterial = "Wood";
                    protoDroneWeight += 0.5;
                    isSuccessful = true;
                    choiceId = " Bird Reservoir - Change frame material to Wood";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            } else if(acceptedSubChoiceNumber == 2) { //make drone smaller and lighter
                timeCost = (float) 1.0;
                financialCost = 50;
                if(checkIfEnoughResources(timeCost, financialCost)){
                    protoDroneWeight -= 0.5;
                    protoDroneSize -= 10;
                    protoNoiseLevel -= 5;
                    isSuccessful = true;
                    choiceId = " Bird Reservoir - Make drone smaller and lighter";
                } else {
                    notEnoughResources(celluloController);
                    return;
                }
            }
        }
        if(latestChoiceId == (int)choices.shipIt){
            if(acceptedSubChoiceNumber == 0){
                timeCost = (float)0.5;
                financialCost = 0;
                if(!checkIfEnoughResources(timeCost, financialCost)){
                    notEnoughResources(celluloController);
                    return; 
                }else{
                    isSuccessful = true;
                    choiceId = " Post office - Eco delivery";
                }
            }else{
                timeCost = (float)0.0;
                financialCost = 50;
                if(!checkIfEnoughResources(timeCost, financialCost)){
                    notEnoughResources(celluloController);
                    return; 
                }else{
                    isSuccessful = true;
                    choiceId = " Post office - Same day delivery";
                }
            }
            
            GameObject allMaps = GameObject.Find("HouseMaps");
                for(int i = 0; i < allMaps.transform.childCount; i++){
                    if(allMaps.transform.GetChild(i).gameObject.name == "Ending"){
                        allMaps.transform.GetChild(i).gameObject.SetActive(true);
                        droneImage.GetComponent<RectTransform>().anchoredPosition3D = new Vector3(-1216, 129, 0);
                        droneImage.GetComponent<RectTransform>().sizeDelta = new Vector2(200, 200);
                    }
                    if(allMaps.transform.GetChild(i).gameObject.name == "PostOffice"){
                        allMaps.transform.GetChild(i).gameObject.SetActive(false);
                    }
                } 
            // Disable original dialogue box
            GameObject.Find("MainTextBox").SetActive(false);
            GameObject.Find("Dialog Box Frame").SetActive(false);
            GameObject.Find("ReturnPad").SetActive(false);
        }
        if(isSuccessful){
            celluloController?.set_leds_green();
        }
        //display updates
        updateAvailableBalanceAndTimeForSubChoices(timeCost, financialCost);
        refreshDroneSpecs();
        //Log data

        dataLogger.LogData("Choice: " + choiceId + " was accepted at time: " + DateTime.Now.ToString("T") + "\n");

        if(choiceId == " Post office - Same day delivery" || choiceId == " Post office - Eco delivery"){
            endingHelper();
        }
    }

    private void endingHelper(){
            stopAllAudio();
            findSortListChoiceTimes();
            logResults();
            endingAudio();
    }

    private void stopAllAudio(){
        AudioSource[] audioSources = GameObject.FindObjectsOfType<AudioSource>();
        foreach(AudioSource audioSource in audioSources){
            audioSource.Stop();
        }
    }

    private void endingAudio(){
        AudioSource[] audioSources = GameObject.FindObjectsOfType<AudioSource>();
        foreach(AudioSource audioSource in audioSources){
            if(audioSource.gameObject.name == "You have made it to the end of the semester"){
                audioSource.Play();
            }
        }
    }

    //Helper function that sorts and then logs in the data log all of the time spent on each choice pad.
    private void findSortListChoiceTimes(){

        // Find all the choice pads in the scene.
        GameObject choicepads = GameObject.Find("ChoicePads");

        foreach (Transform child in choicepads.transform) //Iterate over children of choicepads.
        {
            TraverseSubchildren(child);
        }
        
        // Sort the list based on timeSpent.
        sortedTimeSpentList = sortedTimeSpentList.OrderBy(tuple => tuple.timeSpent).Reverse().ToList();
    }

    private void TraverseSubchildren(Transform currentChild)
    {
        if (currentChild.gameObject.name == "dialoguePad")
        {
            return; // Skip if it's a dialoguePad.
        }

        double? timeSpent = currentChild.GetComponent<ChoicePoint>()?.timeSpent;
        if (timeSpent != null && timeSpent != 0) // If the child has a TimeSpentComponent.
        {
            sortedTimeSpentList.Add((currentChild.GetComponent<ChoicePoint>().choiceStringId, timeSpent));
        }

        // Now recursively check its children.
        foreach (Transform subChild in currentChild)
        {
            TraverseSubchildren(subChild);
        }
    }

    private void logResults()
    {
        //log the data
        dataLogger.LogData("+++++++ End of game ++++++ \n");
        dataLogger.LogData("Results: \n     Time spent on each choice pad, descending order: \n");
        string logMessage = string.Join("\n", sortedTimeSpentList.Select(tuple => $"        choice: {tuple.subChoiceNumber}, Time spent on pad: {tuple.timeSpent} seconds \n"));
        dataLogger.LogData(logMessage);
    }

    //Helper function that handles the event of not enough resources
    private void notEnoughResources(MainCelluloController celluloController)
    {
        dialogueTextBox.text = "Not enough resources!";
        celluloController.set_leds_orange();
    }

    //Contains logic calculate the next text to display in scrollBar
    //Each choice locked in has an according display text
    private void updateMainTabText(Dialogue new_dialogue){
        EnterButton.dialogueTextBox = this.dialogueTextBox;
        EnterButton.dialogue = new_dialogue;
    }
    // Class-level variable to store which specs have changed.


    private void refreshDroneSpecs()
    {
        StringBuilder sb = new StringBuilder("", 400);
        sb.AppendFormat("Prototype drone specs: \n");

        bool shouldStartCoroutine = false;

        shouldStartCoroutine |= AppendFormattedSpec(sb, "Color: ", protoDroneColor, lastProtoDroneColor);
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Weight [kg]: ", string.Format("{0:F1}", protoDroneWeight), string.Format("{0:F1}", lastProtoDroneWeight));
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Size [cm]: ", protoDroneSize.ToString(), lastProtoDroneSize.ToString());
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Drone Frame Material: ", protoFrameMaterial, lastProtoFrameMaterial);
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Battery lifespan: ", protoDroneLifespan.ToString() + " minutes", lastProtoDroneLifespan.ToString() + " minutes");
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Propeller Material: ", protoPropellerMaterial, lastProtoPropellerMaterial);
        shouldStartCoroutine |= AppendFormattedSpec(sb, "Noise level: ", protoNoiseLevel.ToString(), lastProtoNoiseLevel.ToString());

        sb.AppendFormat("\n-----Extra Features----- \n");
        if (has_wetsuit)
        {
            shouldStartCoroutine |= AppendFormattedBoolFeature(sb, "Wet suit available", has_wetsuit, lastHas_wetsuit);
        }
        if (has_manual)
        {
            shouldStartCoroutine |= AppendFormattedBoolFeature(sb, "Drone Manual available", has_manual, lastHas_manual);
        }
        if (has_foldable_propellers)
        {
            shouldStartCoroutine |= AppendFormattedBoolFeature(sb, "Foldable Propellers", has_foldable_propellers, lastHas_foldable_propellers);
        }

        droneSpecsText.text = sb.ToString();

        if (protoDroneColor == "White")
        {
            droneImage.sprite = droneWhiteSpriteImage;
        }
        else if (protoDroneColor == "Purple")
        {
            droneImage.sprite = dronePurpleSpriteImage;
        }

        if (shouldStartCoroutine)
        {
            StartCoroutine(RevertColorAfterDelay());
        }
    }

    private bool AppendFormattedSpec(StringBuilder sb, string label, string currentValue, string lastValue)
    {
        if (currentValue != lastValue)
        {
            sb.AppendFormat("<color=green>" + label + currentValue + "</color>\n");
            return true;
        }
        else
        {
            sb.AppendFormat(label + currentValue + "\n");
            return false;
        }
    }

    private bool AppendFormattedBoolFeature(StringBuilder sb, string feature, bool currentValue, bool lastValue)
    {
        if (currentValue != lastValue && currentValue == true)
        {
            sb.AppendFormat("<color=green>" + feature + "</color>\n");
            return true;
        }
        else if (currentValue)
        {
            sb.AppendFormat(feature + "\n");
            return false;
        }
        return false;
    }

    IEnumerator RevertColorAfterDelay()
    {
        yield return new WaitForSeconds(2);
        refreshDroneSpecs();
        UpdateLastValues();
    }

    private void UpdateLastValues()
    {
    lastProtoDroneColor = protoDroneColor;
    lastProtoDroneWeight = protoDroneWeight;
    lastProtoDroneSize = protoDroneSize;
    lastProtoFrameMaterial = protoFrameMaterial;
    lastProtoDroneLifespan = protoDroneLifespan;
    lastProtoPropellerMaterial = protoPropellerMaterial;
    lastProtoNoiseLevel = protoNoiseLevel;
    lastHas_wetsuit = has_wetsuit;
    lastHas_manual = has_manual;
    lastHas_foldable_propellers = has_foldable_propellers;
    }
    private void PlayConfirmationSound()
    {
        // Find the game object with the name "confirmation"
        GameObject soundObject = GameObject.Find("confirmation");

        // Check if the object exists and has an AudioSource component
        if (soundObject != null)
        {
            AudioSource audioSource = soundObject.GetComponent<AudioSource>();
            if (audioSource != null)
            {
                audioSource.Play();
            }
            else
            {
                Debug.LogWarning("The 'confirmation' GameObject does not have an AudioSource component!");
            }
        }
        else
        {
            Debug.LogWarning("No GameObject named 'confirmation' found in the scene!");
        }
    }

    //Update available time and balance for subchoices
    private void updateAvailableBalanceAndTimeForSubChoices(float timeCost, int financialCost) {
        remainingTime-= timeCost;
        availableBalance -= financialCost;
        remainingTimeText.text = "Time Left: " + remainingTime.ToString("F1") +" Weeks"; 
        availableBalanceText.text = "Balance: " + availableBalance.ToString() +" CHF"; 
         // If the remaining time is less than 1 week, change the color of the text to orange
        if(remainingTime <= 1f ){
            remainingTimeText.color = orange;
        }

        // If the available balance is less than 100, change the color of the text to orange
        if(availableBalance <= 100){
            availableBalanceText.color = orange;
        }
        
    }
    //Update available balance and time for main choices
    private void updateAvailableBalanceAndTimeForMainChoice(int locked_choice_id) {
        remainingTime-= mainChoiceTimeCosts[locked_choice_id];
        availableBalance -= mainChoiceFinancialCosts[locked_choice_id];

        // If the remaining time is less than 1 week, change the color of the text to orange
        if(remainingTime <= 1f ){
            remainingTimeText.color = orange;
        }

        // If the available balance is less than 100, change the color of the text to orange
        if(availableBalance <= 100){
            availableBalanceText.color = orange;
        }

        remainingTimeText.text = "Time Left: " + remainingTime.ToString("F1") +" Weeks";
        availableBalanceText.text = "Balance: " + availableBalance.ToString() +" CHF"; 
        
    }

    public Dialogue computeOutcomeDialogue(){
        int outcomeNum = 0;
        
        StringBuilder sb = new StringBuilder("", 500);
        string sentence = "";
        sb.AppendFormat("Ansley Smith: \n\n");
        sb.AppendFormat("\"");
        if(protoDroneColor.Equals("Blue")) {
             sentence = "The color of the drone is unfortunate because its color blends in with that of" + 
             " the sky, i often lose track of it and then lose time trying to find it.";
             ansleyAudio.Add("The color of drone is unfortunate");
        } else if(protoDroneColor.Equals("White")) {
             sentence = "The white color of the drone is easy to spot in the sky however some birds" + 
             " have attacked the drone, maybe because white is seen as aggressive by some birds." ;
             ansleyAudio.Add("The white color of the drone is easy to spot");    
        } else if(protoDroneColor.Equals("Purple")){
             sentence = "I like that you made the drone purple, most birds are not threatened "
             + "by this color and the drone remains clearly visible to the operator." ;  
             ansleyAudio.Add("I like that you made the drone purple");
        }
        sb.AppendFormat(sentence + "\n\n");
        
        if(protoDroneSize <= 30) {
            sentence = "The size of the drone is small and easy to carry!, however on windy days it" 
            + " is not as stable as previous drones.";
            ansleyAudio.Add("The size of the drone is small");
        } else if(protoDroneSize > 30) {
            sentence  = "The drone is pretty big and unable to fit in my bag, perhaps a carrying case " + 
            "would be useful";
            ansleyAudio.Add("The drone is pretty big");
        }
        sb.AppendFormat(sentence + "\n\n");

        //flight time is influenced by WEIGHT AND BATTERY (baterry shouldnt be in minutes!! thats autonomy)
        //use weight for stability and lfiespan for this
        if(protoDroneLifespan <= 15) {
            sentence =  "Drone was light and easy to carry, but short flying time meant it felt like a lot of " + 
            "work for the brief footage. Although we did get some really great data we couldn’t have got otherwise!";
            ansleyAudio.Add("Drone was light and easy to carry");
        }else if(protoDroneLifespan > 15 && protoDroneLifespan <= 20) {
            sentence = "Long flying time from the big battery was a great improvement from our last drone,"
        + " and the drone was stable in the wind.";
            ansleyAudio.Add("Long flying time from the big battery");
        }else {
            sentence = "This drone is capable of flying and observing birds for about 30 minutes, "+
            "it is a slight improvement from our previous drone and the stability of the drone is about the same."; 
            ansleyAudio.Add("This drone is capable of flying");
        }
        sb.AppendFormat(sentence);
        sb.AppendFormat("\"");
        finalOutcomeDialogueSentences[outcomeNum++] = sb.ToString();
        sb.Clear();

        sb.AppendFormat("Davina Murphy: \n\n");
        sb.AppendFormat("\"");
        if(has_wetsuit) {   
            sentence = "The previous drone we used did not have a wet suit, so we are very satisfied" 
            + " to now we are able to conduct our bird observation even in the rough Scottish weather";
        } else {
            sentence = "Unfortunately that just our previous drone we had, we are not able to use" + 
            " it under rainy conditions.";            
        }
        sb.AppendFormat(sentence + "\n\n");

        if(has_manual) {   
            sentence = "Including the drone manual was super useful, allowing new people to pick it up quickly. " 
            + "Although terminology was a bit technical, so they added in some of their own definitions to make it more accessible";
        } else {
            sentence = "Hard to get started using the drone. Mostly only the 2 PhD student researchers were willing to invest time getting competent, "
            + "we will see if those starting next year also will.";            
        } 
        sb.AppendFormat(sentence + "\n\n");
        

        if(protoPropellerMaterial == "Plastic"){
            sentence = "The plastic propellers of the drone make a lot of noise, and on occasion seems to scare off" + 
            " or disturb some of the birds, however the flexibility of the propellers makes the drone less harmful in case of a collision"
            +" with a bird.";
        } else if(protoPropellerMaterial == "Carbon Fiber"){
            sentence = "Quiet drones appear not to bother birds at all, however the carbon fiber propellers are much harder than"+
            " plastic ones, and we need to be really careful flying it too close to the birds as the propeller could seriously injure a curious or aggressive bird.";            
        } else if(protoPropellerMaterial == "Wood"){
            sentence = "The wooden propellers are very silent and appear not to bother birds at all, "+
            " however they are harder than plastic ones, so i am always afraid of injuring a bird who might fly to close."; 
        }
        sb.AppendFormat(sentence + "\"");
        finalOutcomeDialogueSentences[outcomeNum++] = sb.ToString();
        sb.Clear();


        sb.AppendFormat("Fiona Wattson: \n\n");
        sb.AppendFormat("\"");
        if(has_foldable_propellers) {
            sentence = "The foldable propellers were a nice upgrade, the drone fits much easier into my bag";
        } else {
            sentence = "The drone is quite big and cumbersome to carry over long distances, perhaps" +  
            " using foldable propellers would make it easier to carry in a smaller bag.";
        }    
        sb.AppendFormat(sentence + "\n\n");

        if(protoDroneWeight <= 1.0) {
            sentence =  "Drone was light and nimble.";
        }else if(protoDroneWeight >= 2.0) {
            sentence = "Long flying time from the big battery was a great improvement from our last drone,"
         + " and the drone was stable in the wind."
         + " But overall the drone was too heavy to carry. Most of our researchers are under 160 cm, so the combined weight and size"
         + " made it very difficult to hike with it over wild terrain for 3h. We didn’t take it out very often";
        } else {
            sentence = "In terms of weight, it is a slight improvement from our previous drone and the stability of the drone is about the same."; 
        }
        sb.AppendFormat(sentence);
        sb.AppendFormat("\"");
        finalOutcomeDialogueSentences[outcomeNum++] = sb.ToString();
        sb.Clear();

        //SPECIFIC OUTCOMES AFTER 1 YEAR OF USE:
        if(protoDroneWeight <= 1.0 && protoDroneLifespan <= 10) {
            finalOutcomeDialogueSentences[outcomeNum++] = "Update after 1 year of use: \n"
            + "The drone was used near a nesting colony of elegant terns and unfortunately due to the drones"
            + " short lifespan and high winds that day, we were unable to return the drone in time and it crashed"
            + ", scaring away the colony and abandoning their eggs!.";
        } else if(protoNoiseLevel >= 95) {
             finalOutcomeDialogueSentences[outcomeNum++] = "Update after 1 year of use: \n"
             + "One of our researches flew the drone too close to"
             +" a couple of bird nest's and the high noise levels scared away the parents, unfortunately they never"
             +" returned, and their eggs were abandoned.";
        } else {
            finalOutcomeDialogueSentences[outcomeNum++] = "Update after 1 year of use: \n" 
            + "Although not perfect the drone has been a great help!";
        }

        finalOutcomeDialogueSentences[outcomeNum++] = "Thank you for playing! \n \n Project adapted from Gianni Lodetti\'s original game. \n \n Project Supervisors: Siara Isaac, Daniel Tazadore, Barbara Bruno \n \n Code : Stefan Popescu, Christopher Williams \n \n Funded by EPFL, CHILI and LEARN Labs";
        
        Dialogue outcomeDialogue = new Dialogue();

        outcomeDialogue.sentences = finalOutcomeDialogueSentences;

        
        if(once){
            //log the final outcome dialog.
            dataLogger.LogData("Outcome dialogue: \n");
            for(int i = 0; i < finalOutcomeDialogueSentences.Length -1; i++){
                dataLogger.LogData(finalOutcomeDialogueSentences[i] + "\n");
            }
        once = false;
        }

        return outcomeDialogue;
    }
}
