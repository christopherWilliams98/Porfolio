using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.Mathematics;

public class TerrainGenerator : MonoBehaviour
{
    public int gridWidth = 256;
    public int gridHeight = 256;
    public int gridElevation = 128;
    public float SCALE_FACTOR = 10.0f;
    public int octaves = 10;
    public float persistence = 0.45f;
    public float lacunarity = 3.0f;
    public int seed;
    public Vector2 offset;
    public float plainsThreshold = 0.5f; // Threshold value for plains biome
    public float lakeThreshold = 0.1f; // Threshold value for lake biome
    public float plainsLacunarity = 2.0f; // Lacunarity for plains biome
    public float plainsPersistence = 0.3f; // Persistence for plains biome
    public float mountainLacunarity = 4.0f; // Lacunarity for mountainous biome
    public float mountainPersistence = 0.6f; // Persistence for mountainous biome
    public float mountainVoronoiFrequency = 0.05f; // Frequency of the Voronoi noise for mountainous biome
    public float mountainVoronoiAmplitude = 10f; // Amplitude of the Voronoi noise for mountainous biome
    public float erosionStrength = 0.05f; // Strength of erosion
    public int smoothIterations = 3; // Number of smoothing iterations


    void Start()
    {
        Terrain terrain = GetComponent<Terrain>();
        TerrainData terrainData = CreateTerrain(terrain.terrainData);
        terrainData.size = new Vector3(gridWidth, gridElevation, gridHeight);
        terrainData.heightmapResolution = gridWidth;
        terrain.terrainData = terrainData;
        terrain.terrainData.SetHeights(0, 0, ComputeTerrainElevations());
    }

    TerrainData CreateTerrain(TerrainData terrainData)
    {

        int terrainSize = gridWidth * 2; 
        int heightmapResolution = terrainSize + 1; 

        terrainData.size = new Vector3(gridWidth, gridElevation, gridHeight);
        terrainData.heightmapResolution = heightmapResolution;
        terrainData.SetHeights(0, 0, ComputeTerrainElevations());
        return terrainData;
    }

    float[,] ComputeTerrainElevations()
    {
        // initialize the 2D array that will store the height values for each point in the grid
        float[,] heights = new float[gridWidth, gridHeight];

        // loop over each point in the grid
        for (int x = 0; x < gridWidth; x++)
        {
            for (int z = 0; z < gridHeight; z++)
            {
                PointElevation(heights, x, z);
            }
        }

        // smooth the terrain
        SmoothTerrain(heights);

        return heights;
    }

    private void PointElevation(float[,] heights, int x, int z)
    {
        // calculate the Perlin noise for the current point, based on its x/z position and scale factor
        Vector2 coord = new Vector2((float)x / SCALE_FACTOR, (float)z / SCALE_FACTOR);
        float elevation = PerlinNoise(coord);

        // assign the height value for the current point based on the Perlin noise value
        if (elevation < plainsThreshold)
        {
            // Plains biome
            heights[x, z] = PerlinNoise(coord, plainsLacunarity, plainsPersistence);
        }
        else if (elevation < lakeThreshold)
        {
            // Lake biome
            heights[x, z] = 0f;
        }
        else
        {
            // Mountainous biome
            float mountainPerlinNoise = PerlinNoise(coord, mountainLacunarity, mountainPersistence);
            float mountaiNVoronoiNoise = VoronoiNoise(coord, mountainVoronoiFrequency, mountainVoronoiAmplitude);

            //blend the Perlin and Voronoi noise for mountainous terrain
            heights[x, z] = blendNoise(mountainPerlinNoise, mountaiNVoronoiNoise); // mountainous terrain has variable height
        }
    }

    void SmoothTerrain(float[,] heights)
    {

        for (int i = 0; i < smoothIterations; i++)
        {
            for (int x = 1; x < gridWidth - 1; x++)
            {
                for (int z = 1; z < gridHeight - 1; z++)
                {
                    float centerHeight = heights[x, z];

                    // Calculate average height of surrounding vertices
                    float averageHeight = (heights[x - 1, z] + heights[x + 1, z] + heights[x, z - 1] + heights[x, z + 1]) / 4f;

                    // Smooth the height value with erosion.
                    heights[x, z] = Mathf.Lerp(centerHeight, averageHeight, erosionStrength);
                }
            }
        }
    }

    float PerlinNoise(Vector2 point, float lacunarity = 3.0f, float persistence = 0.45f)
    {
        // Initialize total to accumulate Perlin noise for each octave
        float total = 0;
        // Starting frequency and amplitude for the noise
        float frequency = 1;
        float amplitude = 1;
        // Used to normalize the result
        float maxAmplitude = 0;

        // Create a pseudo-random number generator using the seed
        System.Random prng = new System.Random(seed);

        // Loop over each octave
        for (int i = 0; i < octaves; i++)
        {
            // Calculate the x and y coordinates for the current octave,
            // scaling by frequency (which increases each octave),
            // and adding a random offset (which is different but consistent for each octave)
            float x = point.x * frequency + prng.Next(-100000, 100000) + offset.x;
            float y = point.y * frequency + prng.Next(-100000, 100000) + offset.y;

            // Get the raw Perlin noise value for the current coordinates
            float perlinValue = Mathf.PerlinNoise(x / SCALE_FACTOR, y / SCALE_FACTOR);

            // Apply a smoothstep function to the raw Perlin noise for more gradual transitions
            perlinValue = Mathf.SmoothStep(0, 1, perlinValue);

            // Apply power function to emphasize high areas
            perlinValue = Mathf.Pow(perlinValue, 5f);

            // Add the current octave's noise value to the total,
            total += perlinValue * amplitude;

            // Add the current amplitude to maxAmplitude,
            // which is used to normalize the final result
            maxAmplitude += amplitude;

            // For the next octave, reduce the amplitude and increase the frequency
            amplitude *= persistence;
            frequency *= lacunarity;
        }

        // Normalize the result to the range of -1 to 1
        return total / maxAmplitude;
    }


    float VoronoiNoise(Vector2 point, float frequency, float amplitude)
    {
        return amplitude * (1 - Mathf.PerlinNoise(point.x * frequency, point.y * frequency));
    }

    // Blend two noise values together
    float blendNoise(float mainNoise, float additionaNoise)
    {
        return mainNoise * 0.9f + additionaNoise * 0.1f;
    }
}