using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class MainCelluloController : MonoBehaviour
{
    public CelluloAgent agent;
    public bool wantsInteraction = false;
    private bool playerMenuEnabled = true;

    public GameObject statMenu;

    bool once = false;

    void Update()
    {
        if(!once && agent != null){
            agent.MoveOnIce();
            once = true;
        }  
    }

    // Toggle the player menu
    void TogglePlayerMenuEnabled(){
        playerMenuEnabled = !playerMenuEnabled;
    }

    // Display or hide the stat menu
    private void display_menu(){
        if(statMenu.activeSelf == true){
            statMenu.SetActive(false);
        }
        else{
            statMenu.SetActive(true);
        }
    }


     // Make one Cellulo LED orange
    public void applyChoiceSelectionColors()
    {
        GameObject _leds = agent.transform.Find("Leds").gameObject;
        agent.SetVisualEffect(VisualEffect.VisualEffectConstSingle, new Color(230f/255f, 97f/255f, 0/255f, 1f), 0);
    }

    // Resets all leds to black
    public void reset_leds()
    {
        agent.SetVisualEffect(VisualEffect.VisualEffectConstAll, new Color(0.0f,0f,0.0f,0f), 255);
    }

    // Sets LEDs to white
    public void set_leds_white()
    {
        agent.SetVisualEffect(VisualEffect.VisualEffectConstAll, new Color(1.0f,1.0f,1.0f,1f), 255);
    }

    //set LEDs to green
    public void set_leds_green(){
        agent.SetVisualEffect(VisualEffect.VisualEffectConstAll, new Color(0.0f,1.0f,0.0f,1f), 255);
    }

    //set LEDs to orange
    public void set_leds_orange(){
        agent.SetVisualEffect(VisualEffect.VisualEffectConstAll, new Color(254/255f,97/255f,0.0f,1f), 255);
    }

    // Check if the player is pressing a Cellulo led button
    public int checkButtonPressed(){
        Cellulo robot = agent._celluloRobot;
        if(robot == null){
            return -1;
        }
    
        for(int i = 0; i < 6; i++){
            if(robot.TouchKeys[i] == Touch.LongTouch){
                return i;
            }
        }
        return -1;
    }

}
