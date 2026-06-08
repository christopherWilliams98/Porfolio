Shader "Custom/RayleighSkybox" {
    Properties {
        _SunBrightness("Sun Brightness", Range(0, 100)) = 20
        _Kr("Rayleigh Coefficient", Range(0,0.02)) = 0.0025
        _Km("Mie Coefficient", Range(0,0.01)) = 0.0010
        _LightBrightness("Brightness", Range(0, 10)) = 1.3
        _ColorWaveLengths("Color Wavelengths", Vector) = (0.70, 0.55, .475)
        _AtmosphereRadius("Atmosphere Radius", Range(0,2)) = 1.1
        _PlanetRadius("Planet Radius", Range(0,2)) = 1.0
        _FScaleDepth("Scale Depth", Range(0,1)) = 0.25
        _UseRayleighPhaseFunction("Use Rayleigh phase function (0 = Off, 1 = On)", Int) = 0
        _UseMiePhaseFunction("Use Mie phase function (0 = Off, 1 = On)", Int) = 0
    }

    SubShader {
        Tags { "Queue"="Background" }
        Cull Off 
        ZWrite Off

        Pass {
            // This shader was inspired by Sean O'Neil's shader from GPU Gems 2
            // https://developer.nvidia.com/gpugems/gpugems2/part-ii-shading-lighting-and-shadows/chapter-16-accurate-atmospheric-scattering
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            
            #include "UnityCG.cginc"

            uniform float _LightBrightness;
            uniform float _Kr;
            uniform float _Km;
            uniform float _SunBrightness;
            uniform float3 _ColorWaveLengths;
            uniform float _AtmosphereRadius;
            uniform float _PlanetRadius; 
            uniform float _FScaleDepth;
            uniform int _UseRayleighPhaseFunction;
            uniform int _UseMiePhaseFunction;

            #define PI 3.1415926535897932384626433832795
            #define NUM_SAMPLES 5
            
            static const float fScale = 1./(_AtmosphereRadius-_PlanetRadius);
            static const float fScaleOverScaleDepth = fScale/_FScaleDepth;
            
            // Effect of Rayleigh and Mie scattering on the overall sunlight strength
            static const float fKrESun = _Kr * _SunBrightness;

            // Values required for the later computation of mie and rayleigh scattering
            // ColorWaveLengths represents the wavelengths of red, green and blue
            // light in micrometers
            static const float fKr4PI = _Kr * 4. * PI;
            static const float3 waveLength4 = pow(_ColorWaveLengths, 4);

            // To be passed on to the fragment shader from vertex shader
            struct v2f
            {
                float4 pos: SV_POSITION; // 
                float3 cameraToObject : TEXCOORD0; // Ray direction from the eye (camera) to the object
                float3 color : TEXCOORD1;
            };

            float scale(float fCos)
            {
                float x = 1. - fCos;
                return 0.25 * exp(-0.00287 + x*(0.459 + x*(3.83 + x*(-6.80 + x*5.25))));
            }

            // Calculates the Mie phase function
            half getMiePhase(half eyeCos, half eyeCos2)
            {
                half temp = 1.0 + 0.9801 - 2.0 * (-0.990) * eyeCos;
                temp = pow(temp, pow(0.015,0.65) * 10);
                temp = max(temp,1.0e-4); // prevent division by zero, esp. in half precision
                temp = 1.5 * ((1.0 - 0.9801) / (2.0 + 0.9801)) * (1.0 + eyeCos2) / temp;
                return temp;
            }

            // Vertex shader
            v2f vert (float4 vertex : POSITION)
            {
                // Initialize total color contribution
                float3 color = (0., 0., 0.);

                // Set camera to sea level
                float3 camPos = float3(0., _PlanetRadius, 0.); 

                // Get the (normalized) direction of the ray from the camera position 
                // to the object point in world coordinates
                float3x3 modelViewProjectionMatrix = unity_ObjectToWorld;
                float3 ray = normalize(mul(modelViewProjectionMatrix, vertex.xyz));

                // Calculate the ray's far intersection with the atmosphere
                // We ignore the near intersection since it is not visible from the camera
                float atmR2 = pow(_AtmosphereRadius, 2);
                float planetR2 = pow(_PlanetRadius, 2);
                float camToObjHeight2 = pow(ray.y, 2); 
                float fFar = sqrt(atmR2 + planetR2*camToObjHeight2 - planetR2); 

                // 
                fFar -= _PlanetRadius * ray.y;

                // The ray starts from the camera, we calculate its angle, depth, and offset
                float fStartAngle = dot(ray, camPos) / _AtmosphereRadius;
                float fStartDepth = exp(-1./fScaleOverScaleDepth);
                float fStartOffset = fStartDepth * scale(fStartAngle);

                // Initialize variables for scattering computation
                float fSampleLength = fFar/NUM_SAMPLES;
                float fScaledLength = fSampleLength*fScale;
                float3 sampleRay = ray*fSampleLength;
                float3 samplePoint = camPos + sampleRay * 0.5;

                // Loop through sample points
                float3 sampleColorContributions = float3(0., 0., 0.);

                for(int i = 0; i < NUM_SAMPLES; i++)
                {
                    float fHeight = length(samplePoint);
                    float fDepth = exp(fScaleOverScaleDepth * (_PlanetRadius - fHeight));
                    float fLightAngle = dot(_WorldSpaceLightPos0.xyz, samplePoint) / fHeight;
                    float fCameraAngle = dot(ray, samplePoint) / fHeight;
                    float fScatter = (fStartOffset + fDepth*(scale(fLightAngle) - scale(fCameraAngle)));
                    float3 attenuate = exp(-fScatter * ((1./waveLength4) * fKr4PI));

                    sampleColorContributions += attenuate * (fDepth * fScaledLength);
                    samplePoint += sampleRay;
                }

                // Calculate the final scattering color
                color = sampleColorContributions * ((1./waveLength4) * fKrESun);
                
                // Transform the vertex position to camera space for the fragment shader
                // The function is equivalent to mul(UNITY_MATRIX_MVP, float4(vertex, 1.0))
                // So, a multiplication of the vertex with the model-view-projection matrix
                v2f OUT;
                OUT.pos = UnityObjectToClipPos(vertex);
                OUT.cameraToObject = -ray; 
                OUT.color = _LightBrightness * color;
                return OUT;
            }

            float4 frag (v2f IN) : SV_Target
            {
                float3 cameraToObjectNormalized = normalize(IN.cameraToObject.xyz);
                // Add the Rayleigh phase function. This is optional as the model looks great without it.
                // Its purpose is to compute the amount of light that is dissipated in a particular direction
                // G(theta) = (3/(16*PI)) * (1 + cos^2(theta))
                // Where theta is the angle between the sun and the camera
                float3 rayleighPhaseFunc = (1., 1., 1.);
                if(_UseRayleighPhaseFunction == 1.){
                    float scatteringAngle = dot(cameraToObjectNormalized, _WorldSpaceLightPos0.xyz);
                    rayleighPhaseFunc = ((float)3./((float)16.*PI))*(1 + pow(scatteringAngle, 2));
                }
                float3 skyScatteringWithPhaseFunc = IN.color * rayleighPhaseFunc;
                

                float sunLight = 0.;
                if(_UseMiePhaseFunction == 1){
                    float eyeCos = dot(cameraToObjectNormalized, _WorldSpaceLightPos0.xyz);
                    float eyeCos2 = pow(eyeCos, 2);
                    sunLight = getMiePhase(eyeCos, eyeCos2);
                    }else{
                    // Calculation of sun in the sky
                    // 1. Get the direction from the sun to the camera
                    // 2. Calculate the size of the sun based on its distance
                    // 3. Calculate the sun's intensity based on its size
                    float3 sunToCamera = _WorldSpaceLightPos0.xyz + IN.cameraToObject.xyz;
                    float sunCircle = 1. - smoothstep(0.01, 0.06, length(sunToCamera));
                    sunLight = pow(sunCircle, 2) * _SunBrightness;
                }

                
                // Calculate the final color
                float3 color = skyScatteringWithPhaseFunc + sunLight;
                return float4(color, 1.);

            }
            ENDHLSL
        }
    }
}