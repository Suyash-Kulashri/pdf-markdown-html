```markdown
# LCM500 Series Datasheet

**500 Watts Bulk Front End**

---

## AT A GLANCE

Advanced Energy’s Artesyn LCM500 series provides a wide range of AC-DC embedded power requirements. Featuring high build quality with robust screw terminals, long life, and typical full-load efficiency of greater than 91 percent, these units are ideal for use in industrial and medical applications. They are backed by a comprehensive set of industrial and medical safety approvals and certificates. Variable-speed ‘Smart Fans’ draw on software controls developed by Advanced Energy to match fan speed to the unit’s cooling requirement and load current. Slowing the fan not only saves power but also reduces wear, thus extending its life. 

### SPECIAL FEATURES
- **510 W output power** (600 W at 45°C for 24 V and 36 V models)
- Low cost
- Dimensions: **1.61” x 4.0” x 9.0”** (Dimensions scaled proportionally to the ~167% increase in power)
- **7.1 W/in³**
- Industrial/Medical safety
- Operating temperature: **-40°C to 70°C** with derating
- Optional **5 V @ 2 A** housekeeping
- High efficiency: **91% @ 230 VAC**
- Variable speed “Smart Fans”
- DSP controlled
- Conformal coat option
- Wide adjustment range
- Margin programming
- OR-ing FET
- PMBus compliant

### Compliance
- EMI Class B
- EN61000 Immunity
- RoHS 3
- PMBus

### SAFETY
- UL62368-1, 1598/1433, and 60601-1 Ed 3
- CSA 62368-1
- TUV 62368-1 and 60601-1
- China CCC
- CB Scheme Report/Cert
- CE and UKCA Mark

*Note: LCM500 tested according to the medical standard IEC 60601-1-2 4th Edition.*

---

## ELECTRICAL SPECIFICATIONS

### Input

| Specification              | Value                  |
|----------------------------|------------------------|
| Input voltage range        | **90 to 264 VAC** (Operating) <br> 115/230 VAC (Nominal) |
| Frequency                  | **47 to 63 Hz**, Nominal 50/60 |
| Input fusing               | Internal 10 A fuses, both lines fused |
| Inrush current             | ≤ 20 A peak, cold start at 25°C |
| Power factor               | 0.98 typical, meets EN61000-3-2 |
| Harmonics                  | Meets IEC61000-3-2 requirements |
| Input current              | **5 Arms max input current**, at 90 VAC |
| Hold up time               | **20 ms** minimum for main O/P, at full rated load |
| Efficiency                 | > 91% typical at full load / 230 VAC nominal |
| Leakage current            | < 0.3 mA at 240 VAC |
| Power line transient       | MOV directly after the fuse |
| Isolation                  | Isolation: PRI-Chassis 2500 VDC Basic <br> PRI-SEC 4000 VAC Reinforced 2xMOPP <br> SEC-Chassis 500 VDC |

### Output

| Specification              | Value                  |
|----------------------------|------------------------|
| Output rating              | See table 1            |
| Set point                  | ± 0.5%                 |
| Total regulation range      | Main output ± 2%       |
| Rated load                 | **510 W** (600 W for current Q and U variants) <br> Derate linearly to 50% from 50°C to 70°C |
| Minimum load               | Main output @ 0.0 A <br> 5V VSB @ 0.0 A |
| Output noise (PARD)       | 1% max p-p <br> 100 mV max p-p |
| Output voltage overshoot    | No overshoot/undershoot outside the regulation band during on or off cycle |
| Transient response          | < 300 μSec 50% load step @ 1 A/μs |
| Max units in parallel       | Up to 10               |
| Short circuit protection     | Protected, no damage to occur in bounce mode |
| Remote sense               | Compensation up to 500 mV |
| Forced load sharing        | To within 10% of all shared outputs (Analog sharing control) |
| Overload protection (OCP)  | 105% to 125% <br> 120% to 170% Main output, 5V VSB output |
| Overvoltage protection (OVP)| 125% to 145% <br> 110% to 125% (12 V output, 5V VSB output) |

### ENVIRONMENTAL SPECIFICATIONS

| Specification                | Value                   |
|------------------------------|-------------------------|
| Operating temperature         | -40°C to +70°C, linear derating to 50% from 50°C to 70°C |
| Storage temperature           | -40°C to +85°C         |
| Humidity                     | 10 to 90%, non-condensing. Operating. Conformal coat option available |
| Fan noise                    | < 45 dBA, 80% load at 40°C; Fan Off when unit is inhibited |
| Altitude                     | Operating, 10,000 feet (3048 m) <br> Storage, 30,000 feet |
| Shock                        | MIL-STD-810F 516.5, Procedure I, VI. Storage |
| Vibration                    | MIL-STD-810F 514.5, Cat. 4, 10. Storage |

---

## ORDERING INFORMATION 

| Model Number | Output | Nominal Output Voltage | Set Point Tolerance | Adjustment Range | Current Output | Ripple P/P (0-50 ˚C) | Max Continuous Power | Combined Line/Load Regulation |
|--------------|--------|-----------------------|---------------------|------------------|-----------------|-----------------------|-----------------------|-------------------------------|
| LCM500L     | 12 V   | 12 V                  | ± 0.5%              | 9.6 - 14.4 V     | 25.0 A          | 120 mV               | 510 W                | 2%                            |
| LCM500N     | 15 V   | 15 V                  | ± 0.5%              | 14.25 - 19.5 V   | 20.0 A          | 150 mV               | 510 W                | 2%                            |
| LCM500Q     | 24 V   | 24 V                  | ± 0.5%              | 19.2 - 28.8 V    | 14.5 A          | 240 mV               | 600 W                | 2%                            |
| LCM500U     | 36 V   | 36 V                  | ± 0.5%              |

## Predicted Table Updates

### Table 1
|   0 |   1 |   2 |   3 |
|----:|----:|----:|----:|
|  25 |  50 |  75 | 100 |

**Predicted Change**: The values in Table 1 may change based on trends in the predict for LCM500 series.
