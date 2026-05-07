import { ChatLauncher } from "./ChatLauncher";
import { ChatPanel } from "./ChatPanel";

export function ChatWidget() {
  return (
    <>
      <ChatPanel />
      <ChatLauncher />
    </>
  );
}
