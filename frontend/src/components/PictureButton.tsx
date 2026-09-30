import React from "react";
import {
  Pressable,
  View,
  StyleSheet,
  GestureResponderEvent,
} from "react-native";

import { colors } from "@/constants/theme";

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
    shadowColor: colors.shadow,
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
    backgroundColor: colors.shutter.fill,
    borderColor: colors.shutter.border,
  },
  defaultInner: {
    width: 56,
    height: 56,
    backgroundColor: colors.shutter.core,
  },

  // Pressed State (Blue Tint)
  pressedOuter: {
    width: 85,
    height: 85,
    backgroundColor: colors.shutter.fillPressed,
    borderColor: colors.shutter.borderPressed,
  },
  pressedInner: {
    width: 56,
    height: 56,
    backgroundColor: colors.shutter.corePressed,
  },
});
