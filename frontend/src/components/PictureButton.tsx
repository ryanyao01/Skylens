import React from "react";
import {
  Pressable,
  View,
  StyleSheet,
  GestureResponderEvent,
} from "react-native";

interface PictureButtonProps {
  onPress?: (event: GestureResponderEvent) => void;
}

export const PictureButton: React.FC<PictureButtonProps> = ({ onPress }) => {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.baseOuter,
        pressed ? styles.pressedOuter : styles.defaultOuter,
      ]}
    >
      {({ pressed }) => (
        <View
          style={[
            styles.baseInner,
            pressed ? styles.pressedInner : styles.defaultInner,
          ]}
        />
      )}
    </Pressable>
  );
};

const styles = StyleSheet.create({
  baseOuter: {
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 4,
    borderRadius: 100,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 25 },
    shadowOpacity: 0.25,
    shadowRadius: 25,
    elevation: 10,
  },
  baseInner: {
    borderRadius: 100,
  },

  // Default State (White)
  defaultOuter: {
    width: 85,
    height: 85,
    backgroundColor: "rgba(255, 255, 255, 0.2)",
    borderColor: "#FFFFFF",
  },
  defaultInner: {
    width: 56,
    height: 56,
    backgroundColor: "#FFFFFF",
  },

  // Pressed State (Blue Tint)
  pressedOuter: {
    width: 85,
    height: 85,
    backgroundColor: "rgba(66, 108, 235, 0.2)",
    borderColor: "#426CEB",
  },
  pressedInner: {
    width: 56,
    height: 56,
    backgroundColor: "#426CEB",
  },
});
