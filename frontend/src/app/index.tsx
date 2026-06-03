import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ImageBackground,
} from "react-native";
import { Scan } from "lucide-react-native";

import { PictureButton } from "@/components/PictureButton";

export default function AirViewScreen() {
  return (
    <View style={styles.container}>
      {/* Replace with camera later */}
      <ImageBackground
        source={{
          uri: "https://img.freepik.com/premium-photo/view-from-commercial-jet-airplane-flighting-sunny-day-cloudy-sky_40120-84.jpg",
        }}
        style={styles.cameraBackground}
        imageStyle={{ opacity: 0.8 }}
      >
        {/* Safe Area Overlay for all HUD elements */}
        <View style={styles.hudOverlay}>
          {/* Top Header */}
          <View style={styles.headerRow}>
            <View style={styles.telemetryPill}>
              <Text style={styles.telemetryText}>ALT 34,000 FT</Text>
              <Text style={styles.telemetryText}>SPD 540 KTS</Text>
            </View>
          </View>

          {/* Center Target Reticle */}
          <View style={styles.centerReticleContainer}>
            <View style={styles.targetBox}>
              <Scan
                color="rgba(255, 255, 255, 0.5)"
                size={48}
                strokeWidth={1.5}
              />
            </View>

            <View style={styles.instructionPill}>
              <Text style={styles.instructionText}>POINT AT AIRCRAFT</Text>
            </View>
          </View>

          {/* Bottom Shutter Button */}
          <View style={styles.bottomControls}>
            <PictureButton
              onPress={() => console.log("Camera Shutter Triggered!")}
            />
          </View>
        </View>
      </ImageBackground>
    </View>
  );
}

const styles = StyleSheet.create({
  // Main Layout
  container: {
    flex: 1,
    backgroundColor: "#000000",
  },
  cameraBackground: {
    flex: 1,
  },
  hudOverlay: {
    flex: 1,
    paddingTop: 48, // Adjust for top notch / status bar
    paddingHorizontal: 24,
    paddingBottom: 100, // Keeps it above your bottom tab bar
    justifyContent: "space-between",
  },

  // Header Elements
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginTop: 8,
  },
  telemetryPill: {
    backgroundColor: "rgba(0, 0, 0, 0.4)",
    borderColor: "rgba(255, 255, 255, 0.1)",
    borderWidth: 1,
    borderRadius: 14,
    padding: 12,
    minWidth: 127,
  },
  telemetryText: {
    color: "#00D3F2",
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 0.6,
    // fontFamily: 'Consolas', // Ensure you load this font in Expo
  },
  compassButton: {
    width: 42,
    height: 42,
    backgroundColor: "rgba(0, 0, 0, 0.4)",
    borderColor: "rgba(255, 255, 255, 0.1)",
    borderWidth: 1,
    borderRadius: 21, // Half of width/height makes it a perfect circle
    justifyContent: "center",
    alignItems: "center",
  },

  // Center Reticle Elements
  centerReticleContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  targetBox: {
    width: 256,
    height: 256,
    borderColor: "rgba(255, 255, 255, 0.3)",
    borderWidth: 2,
    borderStyle: "dashed",
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  instructionPill: {
    marginTop: 32,
    backgroundColor: "rgba(0, 0, 0, 0.4)",
    borderRadius: 50, // Creates a fully rounded pill
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  instructionText: {
    color: "rgba(255, 255, 255, 0.8)",
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 1.4,
    // fontFamily: 'Consolas',
  },

  // Bottom Controls
  bottomControls: {
    alignItems: "center",
    paddingBottom: 20,
  },
  shutterOuter: {
    width: 85,
    height: 85,
    backgroundColor: "rgba(255, 255, 255, 0.2)",
    borderColor: "#FFFFFF",
    borderWidth: 4,
    borderRadius: 42.5,
    justifyContent: "center",
    alignItems: "center",
    // Emulating the Figma box-shadow
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 25 },
    shadowOpacity: 0.25,
    shadowRadius: 25,
    elevation: 10, // For Android shadow
  },
  shutterInner: {
    width: 56,
    height: 56,
    backgroundColor: "#FFFFFF",
    borderRadius: 28,
  },
});
