import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface Props {
  mode: "keyword" | "nl";
  onChange: (mode: "keyword" | "nl") => void;
}

export function SearchModeToggle({ mode, onChange }: Props) {
  return (
    <Tabs value={mode} onValueChange={(v) => onChange(v as "keyword" | "nl")}>
      <TabsList>
        <TabsTrigger value="keyword">Keyword Search</TabsTrigger>
        <TabsTrigger value="nl">Natural Language</TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
