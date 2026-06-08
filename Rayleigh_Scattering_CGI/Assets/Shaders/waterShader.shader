Shader "Custom/waterShader"
{
    Properties
    {
        _WaterColor("Color", Color) = (0.02,0.5, 1, 1)
        _Specular("Specular", Range(0,10)) = 4
        _ShineCoeff("Shine Coefficient", Range(0,10)) = 4
        _DiffuseCoefficient("Diffuse Coefficient",Range(0,10)) = 1
        _BumpMap ("Water Normalmap ", 2D) = "" { }
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderQueue"="Transparent"}
        Blend SrcAlpha OneMinusSrcAlpha
        LOD 200
        
        Pass{
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag

            #include "UnityCG.cginc"
            #include "Lighting.cginc"

            struct v2f {
                float4 vertex : SV_POSITION;
                fixed4 color : COLOR;
                float3 worldPos : TEXCOORD1;
                float2 uv : TEXCOORD0;
            };

            struct appdata {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            sampler2D _BumpMap;
            float4 _WaterColor;
            float _Specular;
            float _ShineCoeff;
            float _DiffuseCoeff;
            
            v2f vert(appdata v){
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.color = v.color* _WaterColor;
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target{
                //base color
                fixed4 color = i.color;
                
                //get noramls from normal map
                fixed4 bumps = tex2D(_BumpMap, i.uv); 
                float3 normal = UnpackNormal(bumps);

                //return fixed4(normals, 1.); //these are the normals of the normal map
                //return fixed4(i.normal, 1.); //these are the normals of the plane (only y direction up :))

                //set up vectors we need for lighting 
                float3 specular = float3(0,0,0);
                float3 dirToCam = normalize(_WorldSpaceCameraPos - i.worldPos);
                float3 dirToLight = -normalize(_WorldSpaceLightPos0.xyz);

                //diffuse component
                float3 diffuse = _DiffuseCoeff*color*max(0,dot(normal, _WorldSpaceLightPos0.xyz));
                
                //specular component (blinn-phong)
                float3 halfVec = normalize(dirToCam + dirToLight);
                float ndoth = max(0, dot(normal,halfVec));
                if(ndoth > 0.){
                    specular = _Specular*color.rgb*pow(ndoth, _ShineCoeff);
                }

                //combine diffuse and specular
                color.rgb += diffuse + specular; 
                //make water slightly transparent
                color.a = 0.8; 

                //add some extra fancy specular 
                if(ndoth>0.999){
                    color.rgb = (1.,1.,1.);
                }

                //water dims with sunset
                float lightCos = dot((0., 1., 0.),normalize(_WorldSpaceLightPos0.xyz));
                color.rgb = color * lerp(0.5, 1., lightCos);

                return color*_LightColor0;
            }
            ENDCG
        }
        
    }
}