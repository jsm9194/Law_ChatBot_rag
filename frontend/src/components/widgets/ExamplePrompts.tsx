interface ExamplePromptsProps {
  onSelect: (text: string) => void;
}

const examples = [
  "📌 산업안전보건법에서 응급조치 의무는?",
  "📌 화재 발생 시 사업주의 책임은?",
  "📌 판례: 시설관리 중 사고 사례",
  "📌 검색: 산업안전보건법 개정 일정 알려줘",
];

export default function ExamplePrompts({ onSelect }: ExamplePromptsProps) {
  return (
    <ul className="space-y-2 text-sm text-left">
      {examples.map((text, idx) => (
        <li
          key={idx}
          onClick={() => onSelect(text)}
          className="cursor-pointer hover:text-blue-500 hover:translate-x-1 transition-all duration-150"
        >
          {text}
        </li>
      ))}
    </ul>
  );
}