// The Intelligence Company doctrine kit, browser module (ES module, no dependencies).
// Likelihood terms, confidence chips, lifeline statuses and response ladders for
// every program's pages and for COP. The vocabulary block below is generated from
// vocab/*.json by tools/build_js.py; edit the JSON, not this block.
//
// Rules the display must keep:
// - Store the number; show the ICD 203 term with its band ("Likely (55-80%)").
// - Likelihood and confidence are two separate chips, never one sentence.
// - Grey means no data, never quiet.
// - Actors carry roles as their sources describe them; frames are unknown or neutral, never friend or hostile.

// BEGIN GENERATED VOCAB
export const VOCAB = {
  "version": {
    "likelihood": "1.0",
    "confidence": "1.0"
  },
  "likelihood": [
    {
      "id": "almost_no_chance",
      "step": 0,
      "term": "Almost no chance",
      "synonym": "Remote",
      "lower": 0.01,
      "upper": 0.05,
      "band_label": "01-05%",
      "uk": {
        "term": "Remote chance",
        "band_label": ">0-~5%"
      }
    },
    {
      "id": "very_unlikely",
      "step": 1,
      "term": "Very unlikely",
      "synonym": "Highly improbable",
      "lower": 0.05,
      "upper": 0.2,
      "band_label": "05-20%",
      "uk": {
        "term": "Highly unlikely",
        "band_label": "~10-~20%"
      }
    },
    {
      "id": "unlikely",
      "step": 2,
      "term": "Unlikely",
      "synonym": "Improbable",
      "lower": 0.2,
      "upper": 0.45,
      "band_label": "20-45%",
      "uk": {
        "term": "Unlikely",
        "band_label": "~25-~35%"
      }
    },
    {
      "id": "roughly_even_chance",
      "step": 3,
      "term": "Roughly even chance",
      "synonym": "Roughly even odds",
      "lower": 0.45,
      "upper": 0.55,
      "band_label": "45-55%",
      "uk": {
        "term": "Realistic possibility (no exact equivalent)",
        "band_label": "~40-<50%"
      }
    },
    {
      "id": "likely",
      "step": 4,
      "term": "Likely",
      "synonym": "Probable",
      "lower": 0.55,
      "upper": 0.8,
      "band_label": "55-80%",
      "uk": {
        "term": "Likely or probable",
        "band_label": "~55-~75%"
      }
    },
    {
      "id": "very_likely",
      "step": 5,
      "term": "Very likely",
      "synonym": "Highly probable",
      "lower": 0.8,
      "upper": 0.95,
      "band_label": "80-95%",
      "uk": {
        "term": "Highly likely",
        "band_label": "~80-~90%"
      }
    },
    {
      "id": "almost_certain",
      "step": 6,
      "term": "Almost certain",
      "synonym": "Nearly certain",
      "lower": 0.95,
      "upper": 0.99,
      "band_label": "95-99%",
      "uk": {
        "term": "Almost certain",
        "band_label": "~95-<100%"
      }
    }
  ],
  "confidence": {
    "low": {
      "term": "Low",
      "meaning": "Information is scant, questionable, fragmented or old, or rests on one line of evidence; the judgment could change sharply."
    },
    "moderate": {
      "term": "Moderate",
      "meaning": "Two or more independent lines of evidence agree, with gaps, caveats or assumptions that keep it short of high."
    },
    "high": {
      "term": "High",
      "meaning": "Three or more independent lines agree, few gaps or assumptions, low deception potential, alternatives examined, and a method with a scored track record. Not a certainty."
    }
  },
  "confidence_label": "Rule-based, not statistical",
  "lifeline_status": {
    "unknown": {
      "term": "Unknown",
      "letter": "U",
      "rgb": [
        145,
        147,
        149
      ],
      "hex": "#919395",
      "meaning": "Extent of disruption unknown. Also used when the suite has no data."
    },
    "significant": {
      "term": "Significant impact",
      "letter": "S",
      "rgb": [
        197,
        32,
        56
      ],
      "hex": "#C52038",
      "meaning": "Severe challenges hindering essential services."
    },
    "moderate": {
      "term": "Moderate impact",
      "letter": "M",
      "rgb": [
        251,
        186,
        22
      ],
      "hex": "#FBBA16",
      "meaning": "Disruption to normal pre-incident service; restoration in progress or by temporary means."
    },
    "minimal": {
      "term": "Minimal impact",
      "letter": "OK",
      "rgb": [
        94,
        156,
        66
      ],
      "hex": "#5E9C42",
      "meaning": "Functioning at pre-incident levels, minor disruptions only."
    },
    "baseline": {
      "term": "Administrative / pre-incident",
      "letter": "B",
      "rgb": [
        1,
        82,
        135
      ],
      "hex": "#015287",
      "meaning": "Not an operational status; pre-incident state or no incident."
    }
  },
  "lifelines": {
    "safety_and_security": {
      "name": "Safety and Security",
      "abbr": "SS"
    },
    "food_hydration_shelter": {
      "name": "Food, Hydration, Shelter",
      "abbr": "FHS"
    },
    "health_and_medical": {
      "name": "Health and Medical",
      "abbr": "HM"
    },
    "energy": {
      "name": "Energy",
      "abbr": "E"
    },
    "communications": {
      "name": "Communications",
      "abbr": "C"
    },
    "transportation": {
      "name": "Transportation",
      "abbr": "T"
    },
    "hazardous_materials": {
      "name": "Hazardous Materials",
      "abbr": "HZ"
    },
    "water_systems": {
      "name": "Water Systems",
      "abbr": "W"
    }
  },
  "points": {
    "AD": [
      42.548,
      1.539
    ],
    "AE": [
      23.466,
      54.547
    ],
    "AF": [
      34.164,
      66.497
    ],
    "AG": [
      17.352,
      -61.791
    ],
    "AI": [
      18.243,
      -63.026
    ],
    "AL": [
      40.655,
      20.114
    ],
    "AM": [
      40.459,
      44.801
    ],
    "AO": [
      -12.183,
      17.984
    ],
    "AQ": [
      -79.843,
      35.885
    ],
    "AR": [
      -33.501,
      -64.173
    ],
    "AS": [
      -14.327,
      -170.747
    ],
    "AT": [
      47.519,
      14.131
    ],
    "AU": [
      -24.13,
      134.05
    ],
    "AW": [
      12.517,
      -69.973
    ],
    "AX": [
      60.156,
      19.87
    ],
    "AZ": [
      40.402,
      47.211
    ],
    "BA": [
      44.091,
      18.068
    ],
    "BB": [
      13.164,
      -59.569
    ],
    "BD": [
      24.215,
      89.685
    ],
    "BE": [
      50.785,
      4.8
    ],
    "BF": [
      12.673,
      -1.364
    ],
    "BG": [
      42.509,
      25.157
    ],
    "BH": [
      26.056,
      50.555
    ],
    "BI": [
      -3.333,
      29.917
    ],
    "BJ": [
      10.325,
      2.352
    ],
    "BL": [
      17.902,
      -62.833
    ],
    "BM": [
      32.297,
      -64.764
    ],
    "BN": [
      4.448,
      114.552
    ],
    "BO": [
      -16.666,
      -64.593
    ],
    "BR": [
      -12.099,
      -49.559
    ],
    "BS": [
      26.402,
      -77.147
    ],
    "BT": [
      27.537,
      90.04
    ],
    "BW": [
      -22.103,
      24.179
    ],
    "BY": [
      53.822,
      28.418
    ],
    "BZ": [
      17.202,
      -88.713
    ],
    "CA": [
      60.324,
      -101.911
    ],
    "CD": [
      -1.858,
      23.459
    ],
    "CF": [
      6.99,
      20.907
    ],
    "CG": [
      0.142,
      15.9
    ],
    "CH": [
      46.719,
      7.464
    ],
    "CI": [
      7.491,
      -5.569
    ],
    "CK": [
      -21.216,
      -159.786
    ],
    "CL": [
      -38.152,
      -72.319
    ],
    "CM": [
      4.585,
      12.473
    ],
    "CN": [
      32.498,
      106.337
    ],
    "CO": [
      3.373,
      -73.174
    ],
    "CR": [
      10.065,
      -84.078
    ],
    "CU": [
      21.334,
      -77.976
    ],
    "CV": [
      15.075,
      -23.639
    ],
    "CW": [
      12.145,
      -68.921
    ],
    "CY": [
      34.913,
      33.084
    ],
    "CZ": [
      49.882,
      15.378
    ],
    "DE": [
      50.962,
      9.678
    ],
    "DJ": [
      11.976,
      42.499
    ],
    "DK": [
      55.967,
      9.018
    ],
    "DM": [
      15.459,
      -61.345
    ],
    "DO": [
      19.104,
      -70.654
    ],
    "DZ": [
      27.397,
      2.808
    ],
    "EC": [
      -1.259,
      -78.188
    ],
    "EE": [
      58.725,
      25.867
    ],
    "EG": [
      26.186,
      29.446
    ],
    "EH": [
      23.968,
      -12.63
    ],
    "ER": [
      15.787,
      38.286
    ],
    "ES": [
      40.091,
      -3.465
    ],
    "ET": [
      8.033,
      39.089
    ],
    "FI": [
      63.252,
      27.276
    ],
    "FJ": [
      -17.826,
      177.975
    ],
    "FK": [
      -51.609,
      -58.739
    ],
    "FM": [
      6.888,
      158.234
    ],
    "FO": [
      62.186,
      -7.058
    ],
    "FR": [
      46.696,
      2.552
    ],
    "GA": [
      -0.438,
      11.836
    ],
    "GB": [
      54.403,
      -2.116
    ],
    "GD": [
      12.113,
      -61.68
    ],
    "GE": [
      41.87,
      43.736
    ],
    "GG": [
      49.464,
      -2.562
    ],
    "GH": [
      7.718,
      -1.037
    ],
    "GL": [
      74.319,
      -39.335
    ],
    "GM": [
      13.642,
      -14.998
    ],
    "GN": [
      10.619,
      -10.016
    ],
    "GQ": [
      2.333,
      8.99
    ],
    "GR": [
      39.493,
      21.726
    ],
    "GS": [
      -55.683,
      -31.063
    ],
    "GT": [
      14.982,
      -90.497
    ],
    "GU": [
      13.354,
      144.704
    ],
    "GW": [
      12.164,
      -14.524
    ],
    "GY": [
      5.124,
      -58.943
    ],
    "HK": [
      22.449,
      114.098
    ],
    "HM": [
      -53.103,
      73.505
    ],
    "HN": [
      14.795,
      -86.888
    ],
    "HR": [
      45.806,
      16.372
    ],
    "HT": [
      19.264,
      -72.224
    ],
    "HU": [
      47.087,
      19.448
    ],
    "ID": [
      -0.954,
      101.893
    ],
    "IE": [
      53.079,
      -7.799
    ],
    "IL": [
      30.911,
      34.848
    ],
    "IM": [
      54.221,
      -4.53
    ],
    "IN": [
      22.687,
      79.358
    ],
    "IO": [
      -6.191,
      71.348
    ],
    "IQ": [
      33.094,
      43.262
    ],
    "IR": [
      32.166,
      54.931
    ],
    "IS": [
      64.779,
      -18.674
    ],
    "IT": [
      44.732,
      11.077
    ],
    "JE": [
      49.221,
      -2.09
    ],
    "JM": [
      18.137,
      -77.319
    ],
    "JO": [
      30.805,
      36.376
    ],
    "JP": [
      36.143,
      138.442
    ],
    "KE": [
      0.549,
      37.908
    ],
    "KG": [
      41.669,
      74.533
    ],
    "KH": [
      12.648,
      104.505
    ],
    "KI": [
      1.82,
      -157.385
    ],
    "KM": [
      -11.728,
      43.318
    ],
    "KN": [
      17.337,
      -62.758
    ],
    "KP": [
      39.885,
      126.445
    ],
    "KR": [
      36.385,
      128.13
    ],
    "KW": [
      29.414,
      47.314
    ],
    "KY": [
      19.32,
      -81.241
    ],
    "KZ": [
      49.054,
      68.686
    ],
    "LA": [
      19.432,
      102.534
    ],
    "LB": [
      34.133,
      35.993
    ],
    "LC": [
      13.892,
      -60.98
    ],
    "LI": [
      47.111,
      9.559
    ],
    "LK": [
      7.581,
      80.705
    ],
    "LR": [
      6.447,
      -9.46
    ],
    "LS": [
      -29.48,
      28.247
    ],
    "LT": [
      55.104,
      24.09
    ],
    "LU": [
      49.734,
      6.078
    ],
    "LV": [
      57.067,
      25.459
    ],
    "LY": [
      26.639,
      18.011
    ],
    "MA": [
      31.651,
      -7.187
    ],
    "MC": [
      43.74,
      7.398
    ],
    "MD": [
      47.435,
      28.488
    ],
    "ME": [
      42.803,
      19.144
    ],
    "MF": [
      18.081,
      -63.049
    ],
    "MG": [
      -18.628,
      46.704
    ],
    "MH": [
      7.083,
      171.194
    ],
    "MK": [
      41.558,
      21.556
    ],
    "ML": [
      18.693,
      -2.038
    ],
    "MM": [
      21.574,
      95.804
    ],
    "MN": [
      45.997,
      104.15
    ],
    "MO": [
      22.13,
      113.556
    ],
    "MP": [
      15.188,
      145.734
    ],
    "MR": [
      19.587,
      -9.74
    ],
    "MS": [
      16.737,
      -62.188
    ],
    "MT": [
      35.893,
      14.433
    ],
    "MU": [
      -20.3,
      57.566
    ],
    "MV": [
      4.174,
      73.508
    ],
    "MW": [
      -13.387,
      33.608
    ],
    "MX": [
      23.92,
      -102.289
    ],
    "MY": [
      2.529,
      113.837
    ],
    "MZ": [
      -13.943,
      37.838
    ],
    "NA": [
      -20.575,
      17.108
    ],
    "NC": [
      -21.065,
      165.084
    ],
    "NE": [
      17.446,
      9.504
    ],
    "NF": [
      -29.033,
      167.955
    ],
    "NG": [
      9.44,
      7.503
    ],
    "NI": [
      12.671,
      -85.069
    ],
    "NL": [
      52.422,
      5.611
    ],
    "NO": [
      61.357,
      9.68
    ],
    "NP": [
      28.298,
      83.64
    ],
    "NR": [
      -0.52,
      166.933
    ],
    "NU": [
      -19.046,
      -169.863
    ],
    "NZ": [
      -39.759,
      172.787
    ],
    "OM": [
      22.12,
      57.337
    ],
    "PA": [
      8.722,
      -80.352
    ],
    "PE": [
      -12.977,
      -72.9
    ],
    "PF": [
      -17.628,
      -149.462
    ],
    "PG": [
      -5.695,
      143.91
    ],
    "PH": [
      11.198,
      122.465
    ],
    "PK": [
      29.328,
      68.546
    ],
    "PL": [
      51.99,
      19.49
    ],
    "PM": [
      47.04,
      -56.332
    ],
    "PN": [
      -24.365,
      -128.318
    ],
    "PR": [
      18.235,
      -66.481
    ],
    "PS": [
      32.047,
      35.291
    ],
    "PT": [
      39.607,
      -8.272
    ],
    "PW": [
      7.518,
      134.58
    ],
    "PY": [
      -21.675,
      -60.146
    ],
    "QA": [
      25.237,
      51.144
    ],
    "RO": [
      45.733,
      24.973
    ],
    "RS": [
      44.19,
      20.788
    ],
    "RU": [
      58.249,
      44.686
    ],
    "RW": [
      -1.897,
      30.104
    ],
    "SA": [
      23.807,
      44.7
    ],
    "SB": [
      -8.03,
      159.17
    ],
    "SC": [
      -4.677,
      55.48
    ],
    "SD": [
      16.331,
      29.261
    ],
    "SE": [
      65.859,
      19.017
    ],
    "SG": [
      1.367,
      103.817
    ],
    "SH": [
      -15.95,
      -5.713
    ],
    "SI": [
      46.061,
      14.915
    ],
    "SK": [
      48.734,
      19.05
    ],
    "SL": [
      8.617,
      -11.764
    ],
    "SM": [
      43.934,
      12.441
    ],
    "SN": [
      15.138,
      -14.779
    ],
    "SO": [
      3.569,
      45.192
    ],
    "SR": [
      4.144,
      -55.911
    ],
    "SS": [
      7.23,
      30.39
    ],
    "ST": [
      0.971,
      7.021
    ],
    "SV": [
      13.685,
      -88.89
    ],
    "SX": [
      18.041,
      -63.07
    ],
    "SY": [
      35.007,
      38.278
    ],
    "SZ": [
      -26.534,
      31.467
    ],
    "TC": [
      21.817,
      -71.753
    ],
    "TD": [
      15.143,
      18.645
    ],
    "TF": [
      -49.304,
      69.122
    ],
    "TG": [
      8.807,
      1.058
    ],
    "TH": [
      15.46,
      101.073
    ],
    "TJ": [
      38.2,
      72.587
    ],
    "TL": [
      -8.804,
      125.855
    ],
    "TM": [
      39.855,
      58.677
    ],
    "TN": [
      33.687,
      9.008
    ],
    "TO": [
      -21.21,
      -175.163
    ],
    "TR": [
      39.345,
      34.508
    ],
    "TT": [
      10.999,
      -60.918
    ],
    "TV": [
      -8.514,
      179.21
    ],
    "TW": [
      23.652,
      120.868
    ],
    "TZ": [
      -6.052,
      34.959
    ],
    "UA": [
      49.725,
      32.141
    ],
    "UG": [
      1.973,
      32.949
    ],
    "US": [
      39.538,
      -97.483
    ],
    "UY": [
      -32.961,
      -55.967
    ],
    "UZ": [
      41.694,
      64.005
    ],
    "VA": [
      41.903,
      12.453
    ],
    "VC": [
      13.088,
      -61.336
    ],
    "VE": [
      7.182,
      -64.599
    ],
    "VG": [
      18.427,
      -64.637
    ],
    "VI": [
      17.747,
      -64.779
    ],
    "VN": [
      21.715,
      105.387
    ],
    "VU": [
      -15.372,
      166.909
    ],
    "WF": [
      -14.286,
      -178.137
    ],
    "WS": [
      -13.639,
      -172.438
    ],
    "XK": [
      42.594,
      20.861
    ],
    "YE": [
      15.328,
      45.874
    ],
    "ZA": [
      -29.709,
      23.666
    ],
    "ZM": [
      -14.661,
      26.395
    ],
    "ZW": [
      -18.912,
      29.925
    ]
  },
  "actor_roles": {
    "party": {
      "label": "Party",
      "frame": "unknown"
    },
    "supporter": {
      "label": "Supporter",
      "frame": "unknown"
    },
    "responsible": {
      "label": "Held responsible",
      "frame": "unknown"
    },
    "affected": {
      "label": "Affected",
      "frame": "neutral"
    },
    "civilians": {
      "label": "Civilians",
      "frame": "neutral"
    },
    "third_party": {
      "label": "Third party",
      "frame": "neutral"
    },
    "unknown": {
      "label": "Role unknown",
      "frame": "unknown"
    }
  },
  "actor_types": {
    "government": "Government",
    "armed_forces": "Armed forces",
    "security_service": "Security service",
    "armed_group": "Armed group",
    "criminal_group": "Criminal group",
    "political_group": "Political group",
    "company": "Company",
    "intergovernmental": "Intergovernmental",
    "ngo": "NGO",
    "media": "Media",
    "population": "Population",
    "individual": "Individual",
    "unknown": "Unknown"
  },
  "ladders": {
    "pager": {
      "name": "USGS PAGER earthquake alert",
      "values": {
        "green": {
          "severity": 0,
          "meaning": "No response needed (estimated fatalities 0; losses under US$1M)."
        },
        "yellow": {
          "severity": 2,
          "meaning": "Local or regional response (fatalities 1-99; losses US$1M-100M)."
        },
        "orange": {
          "severity": 3,
          "meaning": "National response (fatalities 100-999; losses US$100M-1B)."
        },
        "red": {
          "severity": 4,
          "meaning": "International response (fatalities 1,000+; losses US$1B+)."
        }
      }
    },
    "usgs_volcano": {
      "name": "USGS Volcano Alert Level",
      "values": {
        "normal": {
          "severity": 0,
          "meaning": "Typical background, non-eruptive state; or activity has ceased and the volcano has returned to that state."
        },
        "advisory": {
          "severity": 1,
          "meaning": "Signs of elevated unrest above known background; or activity has decreased significantly but is watched for renewed increase."
        },
        "watch": {
          "severity": 2,
          "meaning": "Heightened or escalating unrest with increased potential of eruption, timeframe uncertain; or an eruption under way that poses limited hazards."
        },
        "warning": {
          "severity": 4,
          "meaning": "Hazardous eruption imminent, under way or suspected."
        }
      }
    },
    "gdacs": {
      "name": "GDACS alert level",
      "values": {
        "green": {
          "severity": 0,
          "meaning": "Low humanitarian impact expected."
        },
        "orange": {
          "severity": 3,
          "meaning": "Moderate impact; international assistance may be needed."
        },
        "red": {
          "severity": 4,
          "meaning": "Severe impact; international assistance likely needed."
        }
      }
    },
    "cems": {
      "name": "Copernicus Emergency Management Service rapid mapping",
      "values": {
        "activated": {
          "severity": 3,
          "meaning": "Rapid mapping activated for the event."
        },
        "closed": {
          "severity": 1,
          "meaning": "Activation closed."
        }
      }
    },
    "ifrc": {
      "name": "IFRC GO response",
      "values": {
        "dref": {
          "severity": 2,
          "meaning": "Disaster Response Emergency Fund allocation."
        },
        "emergency_appeal": {
          "severity": 3,
          "meaning": "Emergency Appeal launched."
        }
      }
    },
    "easa_czib": {
      "name": "EASA Conflict Zone Information Bulletin",
      "values": {
        "active": {
          "severity": 3,
          "meaning": "Bulletin in force for the airspace."
        },
        "expired": {
          "severity": 0,
          "meaning": "Bulletin lapsed or withdrawn."
        }
      }
    },
    "state_travel_advisory": {
      "name": "US State Department Travel Advisory level",
      "values": {
        "level_1": {
          "severity": 0,
          "meaning": "Exercise normal precautions."
        },
        "level_2": {
          "severity": 1,
          "meaning": "Exercise increased caution."
        },
        "level_3": {
          "severity": 2,
          "meaning": "Reconsider travel."
        },
        "level_4": {
          "severity": 4,
          "meaning": "Do not travel."
        }
      }
    },
    "state_post_posture": {
      "name": "US embassy or consulate staffing posture",
      "values": {
        "normal": {
          "severity": 0,
          "meaning": "Normal operations."
        },
        "authorized_departure": {
          "severity": 2,
          "meaning": "Non-emergency staff and family members may leave at government expense."
        },
        "ordered_departure": {
          "severity": 3,
          "meaning": "Non-emergency staff and family members are ordered to leave."
        },
        "suspended_operations": {
          "severity": 4,
          "meaning": "The post has suspended operations."
        }
      }
    }
  },
  "last_change": {
    "new": "The subject or condition first appeared.",
    "raised": "Its level moved up on its own ladder or across its own threshold.",
    "lowered": "Its level moved down on its own ladder or back across its own threshold.",
    "changed": "Scope, place or wording changed, with the level the same.",
    "ended": "No longer observed or in force.",
    "none": "No change in the program's record: standing for as long as the program has watched."
  },
  "place_basis": {
    "location": "It is, or it happened, there.",
    "subject": "The item is about that country (an advisory, a currency, a sanctions list), wherever it is.",
    "named": "A party is named: a victim's country, a network's home, an operator's origin. A join by place skips it.",
    "zone": "The program's own multi-country zone; counts as one place, not as each country in it."
  },
  "zones": {
    "01_Ukraine_Conflict": {
      "name": "Ukraine Conflict",
      "countries": [
        "UA"
      ]
    },
    "07_Russia_NATO": {
      "name": "Russia-NATO Border",
      "countries": [
        "BY",
        "DK",
        "EE",
        "FI",
        "LT",
        "LV",
        "NO",
        "PL",
        "RU",
        "SE"
      ]
    },
    "02_Taiwan_Strait": {
      "name": "Taiwan Strait",
      "countries": [
        "TW"
      ]
    },
    "08_South_China_Sea": {
      "name": "South China Sea",
      "countries": [
        "PH",
        "VN"
      ]
    },
    "03_Korea_Peninsula": {
      "name": "Korea Peninsula",
      "countries": [
        "KP",
        "KR"
      ]
    },
    "10_Israel_Gaza_Lebanon": {
      "name": "Israel, Gaza & Lebanon",
      "countries": [
        "IL",
        "LB",
        "PS"
      ]
    },
    "11_Iran_Red_Sea": {
      "name": "Iran & Red Sea",
      "countries": [
        "IR",
        "YE"
      ]
    },
    "06_India_Pakistan": {
      "name": "India-Pakistan",
      "countries": [
        "IN",
        "PK"
      ]
    },
    "13_Sudan": {
      "name": "Sudan",
      "countries": [
        "SD"
      ]
    },
    "18_Ethiopia_Eritrea": {
      "name": "Ethiopia & Eritrea",
      "countries": [
        "ER",
        "ET"
      ]
    },
    "19_Somalia": {
      "name": "Somalia",
      "countries": [
        "DJ",
        "SO"
      ]
    },
    "12_Sahel_West_Africa": {
      "name": "Sahel & West Africa",
      "countries": [
        "BF",
        "ML",
        "NE"
      ]
    },
    "14_DRC_Rwanda": {
      "name": "DRC-Rwanda (M23)",
      "countries": [
        "CD",
        "RW"
      ]
    },
    "16_Myanmar": {
      "name": "Myanmar",
      "countries": [
        "MM"
      ]
    },
    "05_Venezuela": {
      "name": "Venezuela",
      "countries": [
        "VE"
      ]
    },
    "15_Cuba": {
      "name": "Cuba",
      "countries": [
        "CU"
      ]
    }
  },
  "zones_retired": {
    "17_Horn_of_Africa": {
      "on": "2026-10-27",
      "into": [
        "18_Ethiopia_Eritrea",
        "19_Somalia"
      ]
    }
  },
  "seas": {
    "adriatic-sea": "Adriatic Sea",
    "aegean-sea": "Aegean Sea",
    "albemarle-sound": "Albemarle Sound",
    "alboran-sea": "Alboran Sea",
    "amazon": "Amazon",
    "amundsen-gulf": "Amundsen Gulf",
    "amundsen-sea": "Amundsen Sea",
    "andaman-sea": "Andaman Sea",
    "antongil-bay": "Antongil Bay",
    "arabian-sea": "Arabian Sea",
    "arafura-sea": "Arafura Sea",
    "arctic-ocean": "Arctic Ocean",
    "bab-el-mandeb": "Bab-el-Mandeb",
    "baffin-bay": "Baffin Bay",
    "bahia-blanca": "Bahía Blanca",
    "bahia-grande": "Bahía Grande",
    "baia-de-sao-marcos": "Baía de São Marcos",
    "baird-inlet": "Baird Inlet",
    "balearic-sea": "Balearic Sea",
    "bali-sea": "Bali Sea",
    "bali-strait": "Bali Strait",
    "baltic-sea": "Baltic Sea",
    "banda-sea": "Banda Sea",
    "barents-sea": "Barents Sea",
    "bass-strait": "Bass Strait",
    "bathurst-inlet": "Bathurst Inlet",
    "bay-of-bengal": "Bay of Bengal",
    "bay-of-biscay": "Bay of Biscay",
    "bay-of-campeche": "Bay of Campeche",
    "bay-of-fundy": "Bay of Fundy",
    "bay-of-mecklenburg": "Bay of Mecklenburg",
    "bay-of-plenty": "Bay of Plenty",
    "beaufort-sea": "Beaufort Sea",
    "bellingshausen-sea": "Bellingshausen Sea",
    "bering-sea": "Bering Sea",
    "bight-of-benin": "Bight of Benin",
    "bight-of-biafra": "Bight of Biafra",
    "bismarck-sea": "Bismarck Sea",
    "black-sea": "Black Sea",
    "boca-grande": "Boca Grande",
    "bohai-sea": "Bohai Sea",
    "bohol-sea": "Bohol Sea",
    "boknafjord": "Boknafjord",
    "bosporus": "Bosporus",
    "bransfield-strait": "Bransfield Strait",
    "bras-dor-lake": "Bras d'Or Lake",
    "bristol-bay": "Bristol Bay",
    "bristol-channel": "Bristol Channel",
    "buli-bay": "Buli Bay",
    "canal-do-norte": "Canal do Norte",
    "canal-do-sul": "Canal do Sul",
    "canal-perigoso": "Canal Perigoso",
    "caribbean-sea": "Caribbean Sea",
    "caspian-sea": "Caspian Sea",
    "celebes-sea": "Celebes Sea",
    "ceram-sea": "Ceram Sea",
    "chaunskaya-bay": "Chaunskaya Bay",
    "chesapeake-bay": "Chesapeake Bay",
    "chukchi-sea": "Chukchi Sea",
    "columbia-river": "Columbia River",
    "cook-strait": "Cook Strait",
    "coral-sea": "Coral Sea",
    "cordova-bay": "Cordova Bay",
    "cumberland-sound": "Cumberland Sound",
    "dampier-strait": "Dampier Strait",
    "dardanelles": "Dardanelles",
    "darnley-bay": "Darnley Bay",
    "davao-gulf": "Davao Gulf",
    "davis-sea": "Davis Sea",
    "davis-strait": "Davis Strait",
    "delaware-bay": "Delaware Bay",
    "denmark-strait": "Denmark Strait",
    "disko-bay": "Disko Bay",
    "dixon-entrance": "Dixon Entrance",
    "dmitry-laptev-strait": "Dmitry Laptev Strait",
    "east-china-sea": "East China Sea",
    "east-korea-bay": "East Korea Bay",
    "east-siberian-sea": "East Siberian Sea",
    "eclipse-sound": "Eclipse Sound",
    "english-channel": "English Channel",
    "flores-sea": "Flores Sea",
    "florida-strait": "Florida Strait",
    "foxe-basin": "Foxe Basin",
    "franklin-bay": "Franklin Bay",
    "frobisher-bay": "Frobisher Bay",
    "fury-and-hecla-strait": "Fury and Hecla Strait",
    "garabogazkol": "Garabogazköl",
    "geographe-bay": "Geographe Bay",
    "george-vi-sound": "George VI Sound",
    "goldsmith-channel": "Goldsmith Channel",
    "great-australian-bight": "Great Australian Bight",
    "greenland-sea": "Greenland Sea",
    "guba-gusinaya": "Guba Gusinaya",
    "gulf-of-aden": "Gulf of Aden",
    "gulf-of-alaska": "Gulf of Alaska",
    "gulf-of-anadyr": "Gulf of Anadyr",
    "gulf-of-aqaba": "Gulf of Aqaba",
    "gulf-of-boothia": "Gulf of Boothia",
    "gulf-of-bothnia": "Gulf of Bothnia",
    "gulf-of-california": "Gulf of California",
    "gulf-of-carpentaria": "Gulf of Carpentaria",
    "gulf-of-corcovado": "Gulf of Corcovado",
    "gulf-of-finland": "Gulf of Finland",
    "gulf-of-gabes": "Gulf of Gabès",
    "gulf-of-guayaquil": "Gulf of Guayaquil",
    "gulf-of-guinea": "Gulf of Guinea",
    "gulf-of-honduras": "Gulf of Honduras",
    "gulf-of-khambhat": "Gulf of Khambhat",
    "gulf-of-kutch": "Gulf of Kutch",
    "gulf-of-lion": "Gulf of Lion",
    "gulf-of-maine": "Gulf of Maine",
    "gulf-of-mannar": "Gulf of Mannar",
    "gulf-of-martaban": "Gulf of Martaban",
    "gulf-of-masirah": "Gulf of Masirah",
    "gulf-of-mexico": "Gulf of Mexico",
    "gulf-of-ob": "Gulf of Ob",
    "gulf-of-oman": "Gulf of Oman",
    "gulf-of-panama": "Gulf of Panama",
    "gulf-of-papua": "Gulf of Papua",
    "gulf-of-penas": "Gulf of Penas",
    "gulf-of-riga": "Gulf of Riga",
    "gulf-of-saint-lawrence": "Gulf of Saint Lawrence",
    "gulf-of-sidra": "Gulf of Sidra",
    "gulf-of-suez": "Gulf of Suez",
    "gulf-of-tehuantepec": "Gulf of Tehuantepec",
    "gulf-of-thailand": "Gulf of Thailand",
    "gulf-of-tomini": "Gulf of Tomini",
    "gulf-of-tonkin": "Gulf of Tonkin",
    "gulf-of-uraba": "Gulf of Urabá",
    "gulf-st-vincent": "Gulf St Vincent",
    "hadley-bay": "Hadley Bay",
    "hall-basin": "Hall Basin",
    "halmahera-sea": "Halmahera Sea",
    "hamilton-inlet": "Hamilton Inlet",
    "hangzhouwan": "Hangzhouwan",
    "hecate-strait": "Hecate Strait",
    "hudson-bay": "Hudson Bay",
    "hudson-strait": "Hudson Strait",
    "husky-lakes": "Husky Lakes",
    "indian-ocean": "Indian Ocean",
    "inutil-bay": "Inútil Bay",
    "ionian-sea": "Ionian Sea",
    "irish-sea": "Irish Sea",
    "james-bay": "James Bay",
    "java-sea": "Java Sea",
    "jones-sound": "Jones Sound",
    "joseph-bonaparte-gulf": "Joseph Bonaparte Gulf",
    "kaliningrad": "Kaliningrad",
    "kamchatka-gulf": "Kamchatka Gulf",
    "kane-basin": "Kane Basin",
    "kao-bay": "Kao Bay",
    "kara-sea": "Kara Sea",
    "kara-strait": "Kara Strait",
    "karaginsky-gulf": "Karaginsky Gulf",
    "kattegat": "Kattegat",
    "kennedy-channel": "Kennedy Channel",
    "khatanga-gulf": "Khatanga Gulf",
    "korea-strait": "Korea Strait",
    "kotzebue-sound": "Kotzebue Sound",
    "kronotsky-gulf": "Kronotsky Gulf",
    "la-perouse-strait": "La Pérouse Strait",
    "labrador-sea": "Labrador Sea",
    "laccadive-sea": "Laccadive Sea",
    "lake-maracaibo": "Lake Maracaibo",
    "lake-mogotoyevo": "Lake Mogotoyevo",
    "lake-pontchartrain": "Lake Pontchartrain",
    "laptev-sea": "Laptev Sea",
    "leyte-gulf": "Leyte Gulf",
    "liddon-gulf": "Liddon Gulf",
    "ligurian-sea": "Ligurian Sea",
    "lincoln-sea": "Lincoln Sea",
    "long-island-sound": "Long Island Sound",
    "lutzow-holm-bay": "Lützow-Holm Bay",
    "mackenzie-bay": "Mackenzie Bay",
    "makassar-strait": "Makassar Strait",
    "maputo-bay": "Maputo Bay",
    "marajo-bay": "Marajó Bay",
    "marguerite-bay": "Marguerite Bay",
    "massachusetts-bay": "Massachusetts Bay",
    "matochkin-strait": "Matochkin Strait",
    "mclure-strait": "M'Clure Strait",
    "mcmurdo-sound": "McMurdo Sound",
    "mediterranean-sea": "Mediterranean Sea",
    "melville-bay": "Melville Bay",
    "minto-inlet": "Minto Inlet",
    "molucca-sea": "Molucca Sea",
    "monterey-bay": "Monterey Bay",
    "mozambique-channel": "Mozambique Channel",
    "murchison-sound": "Murchison Sound",
    "north-atlantic-ocean": "North Atlantic Ocean",
    "north-pacific-ocean": "North Pacific Ocean",
    "north-sea": "North Sea",
    "northwest-passage": "Northwest Passage",
    "norton-sound": "Norton Sound",
    "norwegian-sea": "Norwegian Sea",
    "olenyok-gulf": "Olenyok Gulf",
    "oresund": "Øresund",
    "palk-strait": "Palk Strait",
    "pamlico-sound": "Pamlico Sound",
    "patos-lagoon": "Patos Lagoon",
    "peacock-sound": "Peacock Sound",
    "persian-gulf": "Persian Gulf",
    "philippine-sea": "Philippine Sea",
    "porpoise-bay": "Porpoise Bay",
    "prince-albert-sound": "Prince Albert Sound",
    "prince-of-wales-strait": "Prince of Wales Strait",
    "prince-william-sound": "Prince William Sound",
    "prydz-bay": "Prydz Bay",
    "qiongzhou-strait": "Qiongzhou Strait",
    "queen-charlotte-sound": "Queen Charlotte Sound",
    "queen-charlotte-strait": "Queen Charlotte Strait",
    "ragay-gulf": "Ragay Gulf",
    "red-sea": "Red Sea",
    "richard-collinson-inlet": "Richard Collinson Inlet",
    "rio-de-la-plata": "Río de la Plata",
    "robeson-channel": "Robeson Channel",
    "ronne-entrance": "Ronne Entrance",
    "ross-sea": "Ross Sea",
    "saint-lawrence-river": "Saint Lawrence River",
    "sakhalin-gulf": "Sakhalin Gulf",
    "salish-sea": "Salish Sea",
    "samar-sea": "Samar Sea",
    "san-francisco-bay": "San Francisco Bay",
    "san-jorge-gulf": "San Jorge Gulf",
    "san-matias-gulf": "San Matías Gulf",
    "sargasso-sea": "Sargasso Sea",
    "savu-sea": "Savu Sea",
    "scoresby-sound": "Scoresby Sound",
    "scotia-sea": "Scotia Sea",
    "sea-of-azov": "Sea of Azov",
    "sea-of-crete": "Sea of Crete",
    "sea-of-japan": "Sea of Japan",
    "sea-of-marmara": "Sea of Marmara",
    "sea-of-okhotsk": "Sea of Okhotsk",
    "sea-of-the-hebrides": "Sea of the Hebrides",
    "seno-otway": "Seno Otway",
    "seno-skyring": "Seno Skyring",
    "seto-inland-sea": "Seto Inland Sea",
    "shark-bay": "Shark Bay",
    "shelikhov-gulf": "Shelikhov Gulf",
    "sherman-basin": "Sherman Basin",
    "sibuyan-sea": "Sibuyan Sea",
    "singapore-strait": "Singapore Strait",
    "skagerrak": "Skagerrak",
    "smith-sound": "Smith Sound",
    "sognefjord": "Sognefjord",
    "solomon-sea": "Solomon Sea",
    "south-atlantic-ocean": "South Atlantic Ocean",
    "south-china-sea": "South China Sea",
    "south-pacific-ocean": "South Pacific Ocean",
    "southern-ocean": "Southern Ocean",
    "st-helena-bay": "St. Helena Bay",
    "storfjorden": "Storfjorden",
    "strait-of-belle-isle": "Strait of Belle Isle",
    "strait-of-gibraltar": "Strait of Gibraltar",
    "strait-of-magellan": "Strait of Magellan",
    "strait-of-malacca": "Strait of Malacca",
    "strait-of-tartary": "Strait of Tartary",
    "sulu-sea": "Sulu Sea",
    "sulzberger-bay": "Sulzberger Bay",
    "surigao-strait": "Surigao Strait",
    "szczecin-lagoon": "Szczecin Lagoon",
    "taiwan-strait": "Taiwan Strait",
    "tasman-sea": "Tasman Sea",
    "tayabas-bay": "Tayabas Bay",
    "tikahtnu-inlet": "Tikahtnu Inlet",
    "timor-sea": "Timor Sea",
    "torres-strait": "Torres Strait",
    "trondheimsfjord": "Trondheimsfjord",
    "tsugaru-strait": "Tsugaru Strait",
    "tyrrhenian-sea": "Tyrrhenian Sea",
    "uchiura-bay": "Uchiura Bay",
    "uda-gulf": "Uda Gulf",
    "ungava-bay": "Ungava Bay",
    "uummannaq-fjord": "Uummannaq fjord",
    "vestfjorden": "Vestfjorden",
    "vilkitsky-strait": "Vilkitsky Strait",
    "vincennes-bay": "Vincennes Bay",
    "visayan-sea": "Visayan Sea",
    "viscount-melville-sound": "Viscount Melville Sound",
    "wadden-sea": "Wadden Sea",
    "wager-bay": "Wager Bay",
    "weddell-sea": "Weddell Sea",
    "white-sea": "White Sea",
    "wrigley-gulf": "Wrigley Gulf",
    "wynniatt-bay": "Wynniatt Bay",
    "yana-bay": "Yana Bay",
    "yangtze": "Yangtze",
    "yellow-sea": "Yellow Sea",
    "yenisei-gulf": "Yenisei Gulf",
    "yucatan-channel": "Yucatán Channel"
  }
};
// END GENERATED VOCAB

/** ICD 203 term object for probability p (0 to 1); band edges resolved symmetrically about 0.5. */
/** [lat, lon] label point inside a country (ISO 3166-1 alpha-2), or null. Natural Earth, public domain. */
export function countryPoint(cc) {
  return VOCAB.points[String(cc || "").toUpperCase()] || null;
}

export function termFor(p) {
  if (typeof p !== "number" || !(p >= 0 && p <= 1)) throw new RangeError(`probability must be 0 to 1, got ${p}`);
  const t = VOCAB.likelihood;
  if (p < 0.05) return t[0];
  if (p < 0.2) return t[1];
  if (p < 0.45) return t[2];
  if (p <= 0.55) return t[3];
  if (p <= 0.8) return t[4];
  if (p <= 0.95) return t[5];
  return t[6];
}

/** "Likely (55-80%)" */
export function likelihoodLabel(p) {
  const t = termFor(p);
  return `${t.term} (${t.band_label})`;
}

/** UK yardstick equivalent, for a tooltip. */
export function ukTooltip(p) {
  const t = termFor(p);
  return `UK yardstick: ${t.uk.term} (${t.uk.band_label})`;
}

const EDGE = { high: "solid", moderate: "dashed", low: "dotted" };

/** Confidence chip: {text, meaning, edge}. Shown apart from the likelihood chip. */
export function confidenceChip(level) {
  const c = VOCAB.confidence[level];
  if (!c) throw new RangeError(`unknown confidence level ${level}`);
  return { text: `Confidence: ${c.term}`, meaning: c.meaning, edge: EDGE[level], label: VOCAB.confidence_label };
}

/** Two chips for one judgment, never joined into one sentence. */
export function judgmentChips(item) {
  const chips = [];
  if (typeof item.probability === "number") {
    const t = termFor(item.probability);
    chips.push({ kind: "likelihood", text: likelihoodLabel(item.probability), step: t.step, tooltip: ukTooltip(item.probability) });
  }
  if (item.confidence) chips.push({ kind: "confidence", ...confidenceChip(item.confidence) });
  return chips;
}

/** FEMA lifeline status: {term, letter, hex, meaning}. Unknown status is grey. */
export function lifelineStatus(status) {
  return VOCAB.lifeline_status[status] || VOCAB.lifeline_status.unknown;
}

/**
 * Date-only label for an item whose source gives no time (data_as_of_precision "day" or "month"): "30 Oct 2026" or
 * "June 2025" in en-GB, read in UTC so no zone moves it to the evening before. Null for an exact time, which is shown
 * in the viewer's zone as usual.
 */
export function asOfDateLabel(item, locale) {
  const prec = item && item.data_as_of_precision;
  if (prec !== "day" && prec !== "month") return null;
  const d = new Date(item.data_as_of);
  if (Number.isNaN(d.getTime())) return null;
  const opts = prec === "month"
    ? { month: "long", year: "numeric", timeZone: "UTC" }
    : { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" };
  return d.toLocaleDateString(locale, opts);
}

const UTC_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?Z$/;
const utcDate = (v) => (typeof v === "string" && UTC_RE.test(v) ? new Date(v) : null);

function floorTo(d, prec) {
  const x = new Date(d.getTime());
  if (prec === "hour") x.setUTCMinutes(0, 0, 0);
  if (prec === "day") x.setUTCHours(0, 0, 0, 0);
  if (prec === "month") { x.setUTCDate(1); x.setUTCHours(0, 0, 0, 0); }
  return x;
}

function periodEnd(d, prec) {
  const x = floorTo(d, prec);
  if (prec === "hour") x.setUTCHours(x.getUTCHours() + 1);
  if (prec === "day") x.setUTCDate(x.getUTCDate() + 1);
  if (prec === "month") x.setUTCMonth(x.getUTCMonth() + 1);
  return x;
}

/** {start, end} (Dates, start may be null) of what an item describes in the world, by contract revision 2.1:
 *  event_start to event_end; with no end, to data_as_of (ongoing), or the start alone when it lies after data_as_of
 *  (scheduled); event_time_precision widens each end to its whole hour, day or month. null with no event time.
 *  The same rule as contract.event_interval() in the Python kit. */
export function eventInterval(item) {
  const prec = ["hour", "day", "month"].includes(item && item.event_time_precision) ? item.event_time_precision : null;
  const es = utcDate(item && item.event_start), ee = utcDate(item && item.event_end);
  if (!es && !ee) return null;
  const start = es ? floorTo(es, prec) : null;
  if (ee) return { start, end: periodEnd(ee, prec) };
  const asof = utcDate(item.data_as_of);
  if (!asof || es > asof) return { start, end: prec ? periodEnd(es, prec) : start };
  return { start, end: asof };
}

/** The gazetteer's name for a sea-area slug ("persian-gulf" -> "Persian Gulf"), or null. */
export function seaName(slug) {
  return VOCAB.seas[slug] || null;
}

/** The shared zone list's name for a zone key ("11_Iran_Red_Sea" -> "Iran & Red Sea"); a retired key gives the
 *  names of the zones it went into, joined; null for an unknown key. */
export function zoneName(key) {
  const z = VOCAB.zones[key];
  if (z) return z.name;
  const old = VOCAB.zones_retired[key];
  return old ? old.into.map((k) => VOCAB.zones[k].name).join(" / ") : null;
}

/** A response ladder rung from "ladder:value", e.g. "pager:orange". */
export function ladderRung(stage) {
  const [ladder, value] = String(stage).split(":");
  const l = VOCAB.ladders[ladder];
  if (!l || !l.values[value]) return null;
  return { ladder: l.name, value, ...l.values[value] };
}

const ARROWS = { new: "✦", raised: "↑", lowered: "↓", unchanged: "→", changed: "⇄", withdrawn: "✕" };

/** Change since the last assessment, as an arrow plus words. */
export function changeText(item, priorProbability) {
  const c = item.change_from_prior;
  if (!c) return null;
  let words = { new: "New", raised: "Up", lowered: "Down", unchanged: "Unchanged", changed: "Changed", withdrawn: "Withdrawn" }[c];
  if ((c === "raised" || c === "lowered") && typeof priorProbability === "number" && typeof item.probability === "number") {
    words += ` from ${termFor(priorProbability).term} to ${termFor(item.probability).term}`;
  }
  return { arrow: ARROWS[c], text: words };
}

const RESPONSIBLE = { claimed: "Claims responsibility", reported: "Reported responsible", assessed: "Assessed responsible" };

/** How to draw an actor. The frame is only ever "unknown" or "neutral": nothing is marked hostile. Claims draw hollow. */
export function actorStyle(actor) {
  const r = VOCAB.actor_roles[actor && actor.role] || VOCAB.actor_roles.unknown;
  return { frame: r.frame, hollow: !actor || actor.status_class === "claimed" };
}

/** One line for an actor: "Russian Armed Forces · Party (Russia)", "LockBit · Claims responsibility". */
export function actorLabel(actor) {
  const r = VOCAB.actor_roles[actor.role] || VOCAB.actor_roles.unknown;
  const role = actor.role === "responsible" ? (RESPONSIBLE[actor.status_class] || r.label) : r.label;
  let extra = "";
  if (actor.role === "supporter" && actor.side) extra = ` of ${actor.side}`;
  else if (actor.role === "third_party") extra = actor.function ? ` (${actor.function})` : "";
  else if (actor.side) extra = ` (${actor.side})`;
  return `${actor.name} · ${role}${extra}`;
}

/** Indicator state for drawing: no data is grey and hatched, never blank. */
export function indicatorStyle(state) {
  return {
    present: { label: "Present", fill: "solid" },
    absent: { label: "Absent", fill: "outline" },
    no_data: { label: "No data", fill: "hatched", grey: true },
  }[state] || { label: "No data", fill: "hatched", grey: true };
}

// ---------- Tips: one program reading another's findings (python/tic_doctrine/tips.py) ----------
// The same matching rules as the Python module, for pages that draw tips from the bus themselves. Change detection,
// staleness by the registry and citation stay in Python, where the feeds are built.

function tipPath(item, path) {
  let cur = item;
  for (const part of path.split(".")) {
    if (!cur || typeof cur !== "object" || !(part in cur)) return null;
    cur = cur[part];
  }
  return cur;
}

function tipCompare(v, op, want) {
  if (v === null || v === undefined) return false;
  switch (op) {
    case "eq": return v === want;
    case "ne": return v !== want;
    case "gt": return v > want;
    case "gte": return v >= want;
    case "lt": return v < want;
    case "lte": return v <= want;
    case "in": return Array.isArray(want) && want.includes(v);
    case "contains": return (Array.isArray(v) || typeof v === "string") ? v.includes(want) : false;
    default: return false;
  }
}

/** Whether a bus item (feature properties) meets one interest from doctrine/interests.json. */
export function tipMatches(item, interest) {
  const program = item.program || item.cop_program;
  if (!(interest.programs || []).includes(program)) return false;
  for (const [key, field] of [["tiers", "tier"], ["kinds", "kind"], ["status_class", "status_class"]]) {
    if (interest[key] && interest[key].length && !interest[key].includes(item[field])) return false;
  }
  if (interest.response_stage_prefix && interest.response_stage_prefix.length) {
    const stage = item.response_stage || "";
    if (!interest.response_stage_prefix.some((p) => stage.startsWith(p))) return false;
  }
  const title = (item.title || "").toLowerCase();
  if (interest.title_any && interest.title_any.length && !interest.title_any.some((t) => title.includes(t.toLowerCase()))) return false;
  if ((interest.title_none || []).some((t) => title.includes(t.toLowerCase()))) return false;
  return (interest.where || []).every((w) => tipCompare(tipPath(item, w.path), w.op, w.value));
}

function geomBbox(geom) {
  if (!geom || typeof geom !== "object") return null;
  const pts = [];
  function walk(c) {
    if (!Array.isArray(c) || !c.length) return;
    if (typeof c[0] === "number" && c.length >= 2) { pts.push([c[0], c[1]]); return; }
    for (const x of c) walk(x);
  }
  if (geom.type === "GeometryCollection") {
    for (const g of geom.geometries || []) {
      const b = geomBbox(g);
      if (b) { pts.push([b[0], b[1]], [b[2], b[3]]); }
    }
  } else {
    walk(geom.coordinates);
  }
  if (!pts.length) return null;
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const [lon, lat] of pts) {
    if (lon < w) w = lon;
    if (lon > e) e = lon;
    if (lat < s) s = lat;
    if (lat > n) n = lat;
  }
  return [w, s, e, n];
}

function areaBoxes(boxes, a) {
  const raw = boxes && boxes[a];
  if (!Array.isArray(raw) || !raw.length) return [];
  if (raw.length === 4 && typeof raw[0] === "number") return [raw];
  return raw.filter((b) => Array.isArray(b) && b.length === 4);
}

function boxesOverlap(a, b) {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

/** Tips for one program from bus items: [{interest_id, areas, program, item}], never the program's own items. */
export function tips(items, interestsDoc) {
  const me = interestsDoc.program;
  const areas = interestsDoc.areas || {};
  const boxes = interestsDoc.boxes || {};
  const out = [];
  for (const interest of interestsDoc.interests || []) {
    const wanted = interest.areas && interest.areas.length ? interest.areas : Object.keys(areas);
    for (const item of items) {
      const program = item.program || item.cop_program;
      if (program === me || !tipMatches(item, interest)) continue;
      const cc = item.countries || [];
      const ibbox = geomBbox(item._geometry || item.geometry);
      const inArea = (a) => (areas[a] || []).some((c) => cc.includes(c)) ||
        (ibbox !== null && areaBoxes(boxes, a).some((b) => boxesOverlap(ibbox, b)));
      let hit;
      if (interest.anywhere) hit = wanted.filter(inArea);
      else {
        hit = wanted.filter(inArea);
        if (!hit.length) {
          if (!cc.length && ibbox === null) hit = interest.global ? [] : null;
          else if (!wanted.length) hit = [];
          else hit = null;
        }
      }
      if (hit === null) continue;
      out.push({ interest_id: interest.id, indicator_id: interest.indicator_id || null, areas: hit, program,
        stale: Boolean(item.cop_stale), item });
    }
  }
  return out;
}
