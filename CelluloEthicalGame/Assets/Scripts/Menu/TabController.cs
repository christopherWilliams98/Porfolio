using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using System;
using System.Text;
using UnityEngine.UI;

public class TabController : MonoBehaviour
{
    [SerializeField] private List<GameObject> tabs;
    //For spawning of tab button
    public DialogueTrigger spawnButtonPrefab;
    public GameObject parentOfSpawn;

    //For spawning for tab body
    public GameObject parentOfBodySpawn; //to know where to place the tab in the hierarchy
    public GameObject spawnTabBodyPrefab;
 
    //--
    //Now need to map button text to an index here...
    private string[] choiceFeedbackTexts = {"None", "Locked in 1", 
    "locked in 2", "Locked in 3", "Locked in 4", "Locked in 5", "Locked in 6"};

    //Called by the pressed button(with onClick() method), using as argument "tabBody" the body associated with the button

    public void onTabSwitch(GameObject tabBody) {
        tabBody.SetActive(true);  

        for(int i = 0; i < tabs.Count; i++) {
            if(tabs[i]!= tabBody){
                tabs[i].SetActive(false);
            }
        }
    }

    //spawn new tab (button and body along with its content)
    public void spawnTab(int choiceId, string locked_choice_text, Dialogue spawned_dialogue) {
        DialogueTrigger spawnedTabButton;
        GameObject spawnedTabBody; //new obj for spawned body
        //Spawn a button for the tab
        spawnedTabButton = GameObject.Instantiate(spawnButtonPrefab);
        //set tex of tab button to same as the choice but without the "cost"
        string substring = locked_choice_text.Substring(0, Math.Max(locked_choice_text.IndexOf(':'), 0));
        spawnedTabButton.GetComponentInChildren<TextMeshProUGUI>().text = substring;

        spawnedTabButton.name = "spawnedTabButton_"+ choiceId.ToString();
        spawnedTabButton.transform.SetParent(parentOfSpawn.transform, false);
        spawnedTabButton.gameObject.SetActive(true);

        //Spawn new tab with 
        //Basically for custom content need to make a prefab, with a text field i can modify.. thats it. not soo hard.
        spawnedTabBody = GameObject.Instantiate(spawnTabBodyPrefab);
        spawnedTabBody.name = "spawnedTabBody_"+ choiceId.ToString();
        spawnedTabBody.transform.SetParent(parentOfBodySpawn.transform, false);

        //set dialogue and dialogueTextBox that the button will trigger
        spawnedTabButton.dialogue = spawned_dialogue;
        spawnedTabButton.dialogueTextBox = spawnedTabBody.GetComponentInChildren<TextMeshProUGUI>(); 

        //set spawnedButton to trigger dialogue upon click
        //might be called with new spawnedTabButton everytime.... so only latest is accessible... idk...
        spawnedTabButton.onClick.AddListener(delegate { spawnedTabButton.TriggerDialogue(); });
        //Modify Button to call correct tab body
        spawnedTabButton.onClick.AddListener(delegate { onTabSwitch(spawnedTabBody); });

        //Add new spawned tab to tabs array
        tabs.Add(spawnedTabBody);
        
    }

}
