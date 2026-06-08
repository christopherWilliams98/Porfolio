Shader "Custom/AlienTerrainShader" {
    Properties {
        _MainTex ("Texture", 2D) = "white" {}
        _Height ("Height", Range(0,1)) = 0.2
    }
    SubShader {
        Tags { "RenderType"="Opaque" }
        LOD 100

        CGPROGRAM
        #pragma surface surf BlinnPhong

        #include "UnityCG.cginc"
        #include "Lighting.cginc"

        sampler2D _MainTex;
        float _Height;

        struct Input {
            float2 uv_MainTex;
            float3 worldNormal;
            float3 worldPos;
            INTERNAL_DATA
        };

        // This function generates a Perlin noise value between 0 and 1.
        float noise(float2 uv) {
            return tex2D(_MainTex, uv).r;
        }

        float3 blendColors(float3 color1, float3 color2, float blendFactor, float threshold) {
            float smoothBlendFactor = smoothstep(-threshold, threshold, blendFactor - 0.5);
            return lerp(color1, color2, smoothBlendFactor);
        }

        void surf (Input IN, inout SurfaceOutput o) {
            // Define various colors for different types of terrain
            float3 sandColor = float3(0.95, 0.8, 0.1);
            float3 grassColor1 = float3(0.3, 0.8, 0.4);
            float3 grassColor2 = float3(0.1, 1.0, 1.0);
            float3 grassColor3 = float3(0.0, 0.1, 0.5);
            float3 stoneColor = float3(1, 0, 1);
            float3 soilColor = float3(0.0, 0.3, 0.05);
            float3 rockColor1 = float3(0.3, 0.8, 0.1);
            float3 rockColor2 = float3(0.0, 0.1, 0.0);
            float3 rockColor3 = float3(0.7, 0.5, 0.5);

            // Calculate the steepness and height
            float steepness = 1.1 - IN.worldNormal.y;
            float height = IN.worldPos.y;

            // Use noise to add variety to the grass color
            float3 grassColor = lerp(lerp(grassColor1, grassColor2, noise(IN.worldPos.xz * 1.9)), grassColor3, noise(IN.worldPos.xz * 2.7));

            // Use noise and steepness to blend between rock colors
            float3 rockColor = lerp(lerp(rockColor1, rockColor2, noise(IN.worldPos.xz * 2.1)), rockColor3, noise(IN.worldPos.xz * 2.3));

            // Define color weights based on steepness and height
            float sandWeight = max(0, smoothstep(_Height + 0.1, _Height - 0.1, height));
            float grassWeight = max(0, smoothstep(0.1, 0.4, steepness)); // Grass more present on flatter terrains
            float soilWeight = max(0, smoothstep(0.2, 0.4, steepness));
            float stoneWeight = max(0, smoothstep(0.4, 0.8, steepness)); // Stone and Rock more present on steeper terrains
            float rockWeight = max(0, smoothstep(0.5, 1.0, steepness));  // Adjust these values as per your need



            // Normalize weights so they sum to 1
            float totalWeight = sandWeight + grassWeight + soilWeight + stoneWeight + rockWeight;
            sandWeight /= totalWeight;
            grassWeight /= totalWeight;
            soilWeight /= totalWeight;
            stoneWeight /= totalWeight;
            rockWeight /= totalWeight;

            // Compute final color as a weighted sum of terrain colors
            o.Albedo = sandWeight * sandColor 
            + grassWeight * grassColor 
            + soilWeight * soilColor
            + stoneWeight * stoneColor
            + rockWeight * rockColor;

            // Adding Ambient Light
            o.Albedo += UNITY_LIGHTMODEL_AMBIENT.xyz;

            o.Gloss = 0.6;
            o.Specular = 0.8;
            o.Alpha = 1.0;
        }


        ENDCG
    }
    FallBack "Diffuse"
}
