using UnityEngine;

public class BiplaneControls : MonoBehaviour
{
    public Vector3 com;

    public float speed = 10f;
    public float maxSpeed = 10;
    public float rotationSpeed = 0.05f;
    public float maxRotationSpeed = 1f;
    public float sensitivity = 1f;
    public float rotationSensitivity = 1f;

    private Rigidbody rb;

    private void Start()
    {
        rb = GetComponent<Rigidbody>();

        rb.centerOfMass = com;

        rb.angularVelocity = Vector3.zero;
        rb.drag = 0.5f;
    }

    private void FixedUpdate()
    {
        float moveVertical = Input.GetAxis("Vertical");

        // Add force in the direction the biplane is facing
        if (moveVertical > 0)
        {
            if (Vector3.Dot(rb.velocity, transform.forward) < maxSpeed)
            {
                rb.AddForce(transform.forward * speed * moveVertical);
            }
        }
        else
        {
            rb.AddForce(transform.forward * speed * moveVertical);
        }

        Vector2 screenCenter = new Vector2(Screen.width / 2, Screen.height / 2);
        Vector2 mousePosition = Input.mousePosition;

        //Calculate the relative position of the mouse cursor to the center of the screen
        Vector2 relativeMousePosition = mousePosition - screenCenter;

        //Normalize the relative mouse position to a range between -1 and 1
        relativeMousePosition.x /= screenCenter.x;
        relativeMousePosition.y /= screenCenter.y;

        //Get rotation from both mouse and keyboard inputs
        float rotateHorizontal = Input.GetAxis("Horizontal") * sensitivity;
        float rotateFromMouse = relativeMousePosition.x * sensitivity;

        //Combine both inputs
        float totalRotateHorizontal = rotateHorizontal + rotateFromMouse;

        //Convert the relative position to rotation around the x and z axes
        Vector3 rotation = new Vector3(-relativeMousePosition.y * sensitivity, 0.0f, -totalRotateHorizontal);

        //Apply the rotation directly to the transform
        transform.rotation *= Quaternion.Euler(rotation * rotationSensitivity);

        Vector3 currentRotation = transform.localEulerAngles;
        transform.localEulerAngles = currentRotation;
    }


}
