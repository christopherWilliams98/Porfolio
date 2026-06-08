using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

public class TextDisplay : MonoBehaviour
{
    public GameObject currentLocation;
    
    private string locationText;
    // Start is called before the first frame update
    void Start()
    {
        locationText = "HELLO WORLD";
    }

    // Update is called once per frame
    void Update()
    {
        if(currentLocation.activeSelf == true)
        {
            this.gameObject.SetActive(true);
            this.gameObject.GetComponent<TextMeshProUGUI>().text = locationText;
        }
        else
        {
            this.gameObject.SetActive(false);
        }
    }




}
