using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class ChoicePoint : MonoBehaviour
{
    [SerializeField] private bool triggerActive = false;
    private bool isMakingChoice;
    private string previousTextboxText;
    public string choiceText = "";
    public string choiceStringId;
    public int sentenceNum;
    public int subchoiceNum;
    private bool hasBeenUsed = false;
    private bool hasBeenVisited = false;
    public bool isTutorial = false;
    public AudioSource audioSource;
    public List<AudioSource> audioSources;
    int choice = -1;
    public MainCelluloController celluloController;
    public double timeSpent;

    // Initialize audio sources
    void Start()
    {
        audioSources = new List<AudioSource>(FindObjectsOfType<AudioSource>());
    }

    // Update is called once per frame
    void Update()
    {
        // Do nothing if the choice has already been made
        if(hasBeenUsed){
            return;
        }

        choice = celluloController.checkButtonPressed();

        // If the player's robot is on a choice point, check if they want to interact
        if(triggerActive && isMakingChoice){
            if(choice == 0 || Input.GetKeyDown(KeyCode.F)){
                // Accept
                DialogueManager dialogueManager = FindObjectOfType<DialogueManager>();
                PlayConfirmationSound();

                // TUTORIAL SPECIFIC INTERACTION
                if(this.transform.parent.gameObject.name == "TutorialChoicePads"){
                    //audio
                    StopAllAudio(audioSources);
                    AudioSource acceptedAudio = GameObject.Find("glad to have").GetComponent<AudioSource>();
                    acceptedAudio.Play();
                    celluloController.set_leds_green();
                    sentenceNum++;
                    
                    choiceText = dialogueManager.DisplayNextSentence(sentenceNum);
                    // Enable the final tutorial dialogue pad
                    Transform child = GameObject.Find("TutorialBus").gameObject.transform.GetChild(0);
                    child?.gameObject.SetActive(true);

                    Transform UICanvas = GameObject.Find("UICanvas").gameObject.transform;
                    for(int i = 0; i < UICanvas.childCount; i++){
                        Transform element = UICanvas.GetChild(i);
                        if(element.gameObject.activeSelf == false){
                            element.gameObject.SetActive(true);
                        } 
                    }
                }else{
                    //Debug.Log("celluloController: " + celluloController);
                    //Debug.Log("dialogueManager: " + dialogueManager);

                    // Simply accept
                    dialogueManager.acceptChanges(subchoiceNum);
                }
                hasBeenUsed = true; // Mark the choice point as used so that the choice cannot be repeated
            }
            else{
                timeSpent += Time.deltaTime;
            }
        }else {
            // Do nothing
        }
    }

    // Activate the choice point when a player enters its range
    void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            // When the point is visited, activate the next pad if it exists
            if(!hasBeenVisited){
                hasBeenVisited = true;
                if(this.gameObject.transform.childCount != 0){
                    for(int i = 0; i < this.gameObject.transform.childCount; i++){
                        Transform child = this.gameObject.transform.GetChild(i);
                        if(child != null){
                            if(child.gameObject.name == "HandPointer"){
                                child.gameObject.SetActive(false);
                            }else{
                                child.gameObject.SetActive(true);
                            }
                        }
                    }
                }
            }

            // If this is a choice point (not a dialogue pad), light up cellulo LEDs to indicate its current state
            if(this.name != "DialoguePad"){
                if(!hasBeenUsed){
                    // Light up the choice buttons
                    celluloController.applyChoiceSelectionColors();
                    isMakingChoice = true;
                }
            }

            // Save the current dialogue text in case the player leaves the range of the choice point
            TextMeshProUGUI textBox = GameObject.Find("main_dialog").GetComponent<TextMeshProUGUI>();
            previousTextboxText = textBox.text;

            // Change the dialogue text to the choice text~
            if(choiceText == ""){
                DialogueManager dialogueManager = FindObjectOfType<DialogueManager>();
                choiceText = dialogueManager.DisplayNextSentence(sentenceNum);
                playAudio();
            }else{
                textBox.text = choiceText;
            }
            
            triggerActive = true; // Enable possible interaction with the pad
        }
    }

    // Deactivate the choice point when a player leaves its range
    void OnTriggerExit(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            // Reset colors
            celluloController.reset_leds();

            // Restore the dialogue text
            if(GameObject.Find("main_dialog") != null && !isTutorial){
                GameObject.Find("main_dialog").GetComponent<TextMeshProUGUI>().text = previousTextboxText;
            }
            triggerActive = false;
            isMakingChoice = false;
        }
    }
    
    // Plays the audio attached to the choice pad
    void playAudio(){
        if(audioSource != null){
            StopAllAudio(audioSources);
            audioSource.Play();
            
        }
    }

    //stops all audio from playing
    public static void StopAllAudio(List<AudioSource> sources)
    {
        foreach (AudioSource audioSource in sources)
        {
            if (audioSource.isPlaying)
            {
                audioSource.Stop();
            }
        }
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

}