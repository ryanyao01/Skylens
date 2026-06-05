import React from "react";
import {
  Pressable,
  StyleSheet,
  View,
  GestureResponderEvent,
} from "react-native";
import { LucideIcon } from "lucide-react-native";

interface BlackButtonProps {
  icon?: LucideIcon;
  onPress?: (event: GestureResponderEvent) => void;
}

export const BlackButton: React.FC<BlackButtonProps> = ({
  onPress,
  icon: Icon,
}) => {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.baseContainer,
        pressed ? styles.pressedContainer : styles.defaultContainer,
      ]}
    >
      {({ pressed }) => (
        <View
          style={[
            styles.baseIconWrapper,
            pressed ? styles.pressedIconWrapper : styles.defaultIconWrapper,
          ]}
        >
          {Icon && <Icon color="#FFFFFF" size={pressed ? 18 : 20} />}
        </View>
      )}
    </Pressable>
  );
};

const styles = StyleSheet.create({
  // Shared structural styles
  baseContainer: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    borderRadius: 14,
  },
  baseIconWrapper: {
    justifyContent: "center",
    alignItems: "center",
  },

  // Default State
  defaultContainer: {
    backgroundColor: "#262626",
    paddingVertical: 12,
    paddingHorizontal: 14,
    width: 48,
    height: 44,
  },
  defaultIconWrapper: {
    width: 20,
    height: 20,
  },

  // Pressed State
  pressedContainer: {
    backgroundColor: "#474747",
    paddingVertical: 9,
    paddingHorizontal: 11,
    width: 40,
    height: 36,
  },
  pressedIconWrapper: {
    width: 18,
    height: 18,
  },
});
