using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;


/*
    * This script is attached to the pads in the house maps
    * It is used to teleport the player to the desired house
    * and to return to the main map
*/
public class Interactable_Point : MonoBehaviour
{
    
    [SerializeField] private bool triggerActive = false;
    public GameObject teleportLocation;
    public GameObject allPads;
    public GameObject returnPad;
    public GameObject choicePads;
    public MainCelluloController celluloController;
    public CelluloGameController gameController;
    private string temp;
    private int cooldown;
    public bool isTutorial = false;
    public bool isEnding = false;
    public int sentenceNum;
    private bool once = true;
    public AudioSource enterSound;
    private AudioSource greetings;


    private void Update()
    {
        // Cooldown for pad interaction in order to prevent spamming with the cellulo long press
        if(cooldown > 0){
          cooldown--;
        }

        if(once && isTutorial){
            // Lock in the player's choice for the tutorial
            gameController.lockInChoice();
            greetings = GameObject.Find("Greetings").GetComponent<AudioSource>();
            greetings.Play();
            once = false;
        }

        int choice = celluloController.checkButtonPressed();

        if(isEnding && triggerActive && cooldown == 0){
            // Check if the ending is active and the trigger is active, and the cooldown has expired
            if(Input.GetKeyDown(KeyCode.Space) || choice != -1){
                endingHandler();
                cooldown = 300; // Set cooldown to 300 frames
            }
            return; 
        }

        // Check if player wants to interact with the pad
        if(triggerActive && (Input.GetKeyDown(KeyCode.Space) || choice != -1 ) && cooldown == 0)
        {
            cooldown = 300; // Set cooldown to 300 frames
            Interact(); 
        }
    }

    private IEnumerator PlaySoundsSequentially(string[] audioNames)
    {

        AudioSource[] allAudioSources = FindObjectsOfType<AudioSource>();

        // Stop all audio sources
        foreach (AudioSource audioSource in allAudioSources)
        {
            audioSource.Stop();
        }

        // Play the audio sources in the order specified in the audioNames array

        foreach (string audioName in audioNames)
        {
            foreach (AudioSource audioSource in allAudioSources)
            {

                if (audioSource.name == audioName)
                {
                    audioSource.Play();
                    while (audioSource.isPlaying)
                    {
                        yield return null;  // Wait until the clip finishes playing
                    }
                    break;  // Once we found and played the right audio source, move to the next name
                }
            }
        }
    }

    public void endingHandler()
    {
        // Find the DialogueManager in the scene
        DialogueManager dialogueManager = FindObjectOfType<DialogueManager>();

        // Compute the outcome dialogue using the game controller
        Dialogue dialogue = gameController.computeOutcomeDialogue();

        // Find the text box for displaying the ending dialogue
        TextMeshProUGUI textBox = GameObject.Find("ending_dialog").GetComponent<TextMeshProUGUI>();

        if(sentenceNum == 0){
            // If it's the first sentence, start the dialogue with the computed dialogue and display it in the text box
            dialogueManager.StartDialogue(dialogue, textBox);
            sentenceNum++;

        }
        else{
            // If it's not the first sentence, display the next sentence in the dialogue
            dialogueManager.DisplayNextSentence(sentenceNum++);
        }

        // Find the game object that contains all the scientists
        GameObject allScientists = GameObject.Find("Scientists");

        switch(sentenceNum){
            case 1:

                StartCoroutine(PlaySoundsSequentially(gameController.ansleyAudio.ToArray()));
                break;
            case 2:
                // Switch the sprite of scientists based on the sentence number
                for(int i = 0; i < allScientists.transform.childCount; i++){
                    if(allScientists.transform.GetChild(i).gameObject.name == "Ansley Smith"){
                        allScientists.transform.GetChild(i).gameObject.SetActive(false);
                    }
                    if(allScientists.transform.GetChild(i).gameObject.name == "Davina Murphy"){
                        allScientists.transform.GetChild(i).gameObject.SetActive(true);
                    }
                }
                break;
            case 3: 
                // Switch the sprite of scientists based on the sentence number
                for(int i = 0; i < allScientists.transform.childCount; i++){
                    if(allScientists.transform.GetChild(i).gameObject.name == "Davina Murphy"){
                        allScientists.transform.GetChild(i).gameObject.SetActive(false);
                    }
                    if(allScientists.transform.GetChild(i).gameObject.name == "Fiona Wattson"){
                        allScientists.transform.GetChild(i).gameObject.SetActive(true);
                    }
                }
                break;
        }
    }

    // Activate pad interaction when a player enters its range// Activate pad interaction when a player enters its range
    public void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            
            triggerActive = true;
            celluloController.set_leds_white();

            if(isEnding){
                // If it's an ending pad, return without making any changes as this is handled in ending handler
                return;
            }
            // Find the text box for displaying the main dialogue
            TextMeshProUGUI textBox = GameObject.Find("main_dialog").GetComponent<TextMeshProUGUI>();
            List<AudioSource> audioSources = new List<AudioSource>(FindObjectsOfType<AudioSource>());

            // Store the current text in the text box
            temp = textBox.text;

            string interactInstructionString = "\n\n\nTouch and hold any light to interact";

            switch(this.gameObject.name){

                case "ReturnPad":
                    // Set the text for the ReturnPad
                    textBox.text = "To Dufftown" + interactInstructionString;
                    break;

                case "TechShopPad":
                    // Set the text for the TechShopPad
                    textBox.text = "Consult drone expert \n\n" + "COST: 0.5 weeks" + interactInstructionString;
                    break;
                    
                case "OrnithologistPad":
                    // Set the text for the OrnithologistPad
                    textBox.text = "Consult ornithologist \n\n" + "COST: 0.5 weeks" + interactInstructionString;
                    break;

                case "CityParkPad":
                    // Set the text for the CityParkPad
                    textBox.text = "Test drone in city park \n\n" + "COST: 0.5 weeks" + interactInstructionString;
                    break;
                
                case "ExternalLocationPad":
                    // Set the text for the ExternalLocationPad
                    textBox.text = "Test drone on external location (in Scottish Highlands),  \n\n" + "COST: 1 week" + interactInstructionString;
                    break;

                case "CityHallPad":
                    // Set the text for the CityHallPad
                    textBox.text = "Consult local council \n\n" + "COST: 1 week" + interactInstructionString;
                    break;

                case "BirdReservoirPad":
                    // Set the text for the BirdReservoirPad
                    textBox.text = "Consult bird reservoir director \n\n" + "COST: 1 week" + interactInstructionString;
                    break;

                case "PostOfficePad":
                    // Set the text for the PostOfficePad
                    textBox.text = "Enter the post office \n\n" + "COST: Free to visit" + interactInstructionString;
                    break;

                case "TutorialPad":
                    // Set the text and play an audio for the TutorialPad
                    textBox.text = "Amazing work! These grey doorway pads are used to enter locations in the game, and will display information about their respective locations when your robot is on top of them. To interact with the grey pad, please touch and hold any of the white lights on the robot.";
                    AudioSource amazing = GameObject.Find("Amazing").GetComponent<AudioSource>();
                    if(!amazing.isPlaying && !greetings.isPlaying){
                        amazing.Play();
                    }
                    break;

                case "SkipTutorialPad":
                    // Set the text for the SkipTutorialPad
                    textBox.text = "If you know how to operate a cellulo robot and you are already familiar with the game, you can skip the tutorial by proceeding through this pad.";
                    ChoicePoint.StopAllAudio(audioSources);
                    break;

                case "TutorialReturnPad":
                    // Set the text and play an audio for the TutorialReturnPad
                    textBox.text = "You're all set to go! Home pads like this one allow you return to the main map once you're done making choices in a location. To interact with the pad, touch and hold any of the white lights on the robot, just as you would on a grey doorway pad. When you're ready, give it a try!\nThis will start the game.";
                    AudioSource allSet = GameObject.Find("all set to go").GetComponent<AudioSource>();
                    ChoicePoint.StopAllAudio(audioSources);
                    allSet.Play();
                    break;

                default:
                
                    break;
            }
        }
    }

    // Deactivate pad interaction when a player leaves its range
    public void OnTriggerExit(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            if(!isTutorial && !isEnding){
                GameObject.Find("main_dialog").GetComponent<TextMeshProUGUI>().text = temp;
            }
            triggerActive = false;
            celluloController.reset_leds();
        }
    }

    // Teleport player to the desired house or return to the main map
    public void Interact()
    {

        // enable the dialogue box
        gameController.enableDialogueBox(true);

        // Disable the pad interaction
        triggerActive = false;

        // Play the enter sound
        if(!isEnding)
        enterSound.Play();

        // Find the drone image
        if(GameObject.Find("DroneImage") != null){
            RectTransform droneImage = GameObject.Find("DroneImage").GetComponent<RectTransform>();
        }

        celluloController.reset_leds();

        if(this.gameObject.name == "SkipTutorialPad"){
            // Skip the tutorial
            Transform UICanvas = GameObject.Find("UICanvas").gameObject.transform;

            for(int i = 0; i < UICanvas.childCount; i++){
                Transform element = UICanvas.GetChild(i);
                if(element.gameObject.activeSelf == false){
                    element.gameObject.SetActive(true);
                } 
            }
        }

        if(this.gameObject.name == "ReturnPad" || this.gameObject.name == "TutorialReturnPad" || this.gameObject.name == "SkipTutorialPad")
        {
            if(this.gameObject.name != "ReturnPad"){
                DateTime now = DateTime.Now;
                gameController.LogDataViaController("=-=-=-= Log for game session started at time:   " + now.ToString("yyyy-MM-dd HH:mm:ss") + "=-=-=-= \n\n");
            }
            else{
                gameController.LogDataViaController("Location left at time: " + DateTime.Now.ToString("T") + "\n");
            }

            // Enable all other house pads, disable return pad and choice pads
            if(allPads!=null){
                allPads.SetActive(true);

            }  
            if(returnPad != null){
                returnPad.SetActive(false);
                
            } 
            foreach(Transform choicePad in GameObject.Find("ChoicePads").transform){
                if(choicePad.gameObject.activeSelf == true){
                    choicePad.gameObject.SetActive(false);

                }
            }

            // Clear the dialogue box
            TextMeshProUGUI textBox = GameObject.Find("main_dialog").GetComponent<TextMeshProUGUI>();
            textBox.text = "";

             TextMeshProUGUI skipText = GameObject.Find("Skip_text").GetComponent<TextMeshProUGUI>();
            skipText.text = "";

            //set all the house maps to inactive
            foreach(Transform house in GameObject.Find("HouseMaps").transform)
            {
                if(house.gameObject.activeSelf == true){
                    house.gameObject.SetActive(false);
                }
            }
        }
        
        else{
            // Enter the desired house 
            teleportLocation?.SetActive(true);

            if(teleportLocation.name == "TutorialBus"){
                TextMeshProUGUI skipText = GameObject.Find("Skip_text").GetComponent<TextMeshProUGUI>();
                skipText.text = "";
            }

            // Move the drone while testing in the city park
            if(teleportLocation.name == "CityPark"){
                GameObject droneImage = GameObject.Find("DroneImage");
                if(droneImage != null){
                    //droneImage.GetComponent<RectTransform>().anchoredPosition3D = new Vector3(-947f, -331f, 0);
                }
            }

            // Disable all other house pads 
            if(allPads != null){
                allPads.SetActive(false);
            }
            // Enable the choice pads
            if(choicePads != null){
                choicePads.SetActive(true);
            }
            //enable the return pad
            if(returnPad != null){
                returnPad.SetActive(true);
            } 
            gameController.lockInChoice();

            gameController.LogDataViaController("Location: " + teleportLocation.name + " - was entered at time: " + DateTime.Now.ToString("T") + "\n");

        }
    }
    
}
