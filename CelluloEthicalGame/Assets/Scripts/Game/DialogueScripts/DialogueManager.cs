using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.SceneManagement;

public class DialogueManager : MonoBehaviour
{
    public Button continueButton; 
    public Button acceptButton; //Update drones ranges and and go to next sentence if there is one.
    public Button refuseButton; //same as accept but doesnt updateDroneRanges
    public CelluloGameController gameController; //Needed to notify gameController that drone rangesAndBalance can be updated based on choice to accept or refuse.
    //Alternatively choice could just notify gameController.acceptRefuseChoiceMade();
    private TextMeshProUGUI dialogueText;
    public bool finishedDialogue = false;
    private List<string> sentences; //Load sentences as read through dialog

    private bool waitTillFinishTyping = false; //Equals true when sentence finished typing out on screen, else false.

    public Button replayButton;

    void Start() {
        sentences = new List<string>();
    }

    /**
    Setup dialogue sentences and dialogue box and begin by displaying first sentence.
    */
    public void StartDialogue(Dialogue dialogue, TextMeshProUGUI dialogueTextBox){
        finishedDialogue = false;
        sentences.Clear(); //clear previous 
        dialogueText = dialogueTextBox;
        foreach(string sentence in dialogue.sentences) {
            sentences.Add(sentence);
        }
        DisplayNextSentence();
    }
    
    /**
    Display next sentence in queue
    */
    public string DisplayNextSentence(int sentenceNum = 0) {
        // If reached end of sentence queue
        if(sentences.Count == 0) {
            finishedDialogue = true;
            return "";
        } 

        string sentence = sentences[sentenceNum];
        //Can only display next sentence if finished typing out the previous sentence
        if(waitTillFinishTyping == false) {
            
            waitTillFinishTyping = true;
            //StopAllCoroutines();//Stop if click continue before last coroutine ended
            StartCoroutine(TypeSentence(sentence));
        }
         return sentence;
    }

    //Code for animating the typing of sentence letter by letter
    IEnumerator TypeSentence(string sentence) {
        dialogueText.text = "";
        foreach(char letter in sentence.ToCharArray()) {
            dialogueText.text += letter;
            yield return new WaitForSeconds(0.005f);
        }
        waitTillFinishTyping = false;
    }

    public void acceptChanges(int acceptedSubChoiceNumber){
        gameController.updateDroneRangesAndResources(acceptedSubChoiceNumber);  //update display of drone Ranges and balance
    }
}
