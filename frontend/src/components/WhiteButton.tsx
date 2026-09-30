import React from "react";
import {
  Text,
  Pressable,
  StyleSheet,
  GestureResponderEvent,
} from "react-native";

import { colors } from "@/constants/theme";

interface WhiteButtonProps {
  text?: string;
  onPress?: (event: GestureResponderEvent) => void;
}

export const WhiteButton: React.FC<WhiteButtonProps> = ({
  text = "Button",
  onPress,
}) => {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.baseContainer,
        styles.defaultContainer,
        pressed && styles.pressedContainer,
      ]}
    >
      <Text style={[styles.baseText, styles.text]}>{text}</Text>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  baseContainer: {
    justifyContent: "center",
    alignItems: "center",
    borderRadius: 14,
  },
  baseText: {
    // fontFamily: 'Segoe UI Symbol',
    color: colors.button.primaryText,
    textAlign: "center",
    userSelect: "none",
  },

  // Default State
  defaultContainer: {
    backgroundColor: colors.button.primary,
    paddingVertical: 12,
    paddingHorizontal: 50,
  },
  text: {
    fontSize: 14,
    lineHeight: 20,
  },

  // Pressed State
  pressedContainer: {
    backgroundColor: colors.button.primaryPressed,
    transform: [{ scale: 0.93 }],
  },
});
