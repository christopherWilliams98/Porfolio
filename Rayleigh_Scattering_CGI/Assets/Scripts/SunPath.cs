using UnityEngine;

public class SunPath : MonoBehaviour
{
    [Tooltip("Minutes per second that pass")]
    public float timeScale;

    public Material skyboxMaterial;

    // Kr values for different times
    public float krDay = 0.001f;
    public float krNight = 0.01f;

    // Times (in degrees of rotation)
    public float sunriseTime = 30.0f;
    public float middayTime = 90.0f;
    public float sunsetTime = 140.0f;

    void Update()
    {
        float angle = Time.deltaTime / 360 * timeScale;
        transform.Rotate(angle, 0, 0);

        // Get the current rotation in the range [0, 360]
        float currentRotation = transform.eulerAngles.x;
        currentRotation = (currentRotation > 180) ? currentRotation - 360 : currentRotation;

        float targetKr;
        if (currentRotation < sunriseTime || currentRotation >= sunsetTime)
        {
            targetKr = krNight;
        }
        else if (currentRotation >= sunriseTime && currentRotation < middayTime)
        {
            // Map currentRotation in the range [krNight, krDay]
            targetKr = Map(currentRotation, sunriseTime, middayTime, krNight, krDay);
        }
        else
        {
            // Map currentRotation in the range [krDay, krNight]
            targetKr = Map(currentRotation, middayTime, sunsetTime, krDay, krNight);
        }

        // Apply the calculated Kr value
        skyboxMaterial.SetFloat("_Kr", targetKr);
    }

    // Map val from range [A, B] to [a, b]
    float Map(float val, float A, float B, float a, float b)
    {
        return (val - A) * (b - a) / (B - A) + a;
    }
}
