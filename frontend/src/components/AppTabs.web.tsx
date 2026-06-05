import {
  Tabs,
  TabList,
  TabTrigger,
  TabSlot,
  TabTriggerSlotProps,
  TabListProps,
} from "expo-router/ui";
import { Pressable, View, Text, StyleSheet } from "react-native";
import { BookOpen, Globe, Scan, LucideIcon } from "lucide-react-native";

export default function AppTabs() {
  return (
    <Tabs>
      <TabSlot style={{ height: "100%" }} />
      <TabList asChild>
        <CustomTabList>
          <TabTrigger name="globe" href="/globe" asChild>
            <TabButton icon={Globe}>Globe</TabButton>
          </TabTrigger>
          <TabTrigger name="index" href="/" asChild>
            <TabButton icon={Scan}>AR View</TabButton>
          </TabTrigger>
          <TabTrigger name="deepDive" href="/deepDive" asChild>
            <TabButton icon={BookOpen}>Deep Dive</TabButton>
          </TabTrigger>
        </CustomTabList>
      </TabList>
    </Tabs>
  );
}

interface CustomTabButtonProps extends TabTriggerSlotProps {
  icon: LucideIcon;
}

export function TabButton({
  children,
  isFocused, // Expo Router automatically provides this state
  icon: Icon,
  ...props
}: CustomTabButtonProps) {
  const currentColor = isFocused ? "#FFFFFF" : "#737373";

  return (
    <Pressable {...props} style={styles.tabButtonContainer}>
      <View style={styles.iconWrapper}>
        <Icon color={currentColor} size={24} strokeWidth={2} />
      </View>
      <Text style={[styles.tabButtonText, { color: currentColor }]}>
        {children}
      </Text>
    </Pressable>
  );
}

export function CustomTabList(props: TabListProps) {
  return (
    <View {...props} style={styles.tabListContainer}>
      {props.children}
    </View>
  );
}

const styles = StyleSheet.create({
  tabListContainer: {
    position: "absolute",
    bottom: 0,
    width: "100%",
    height: 80,
    backgroundColor: "#171717", // Cod Gray
    borderTopWidth: 1,
    borderTopColor: "#262626", // Mine Shaft
    paddingHorizontal: 24,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  tabButtonContainer: {
    width: 80,
    height: 43,
    alignItems: "center",
    justifyContent: "center",
  },
  iconWrapper: {
    width: 24,
    height: 28,
    alignItems: "center",
    justifyContent: "flex-start",
  },
  tabButtonText: {
    fontSize: 10,
    lineHeight: 15,
    letterSpacing: 0.25,
    textTransform: "uppercase",
  },
});
