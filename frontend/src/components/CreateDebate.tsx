'use client';

import { useState } from 'react';

export default function CreateDebate({
  onCreated,
}: {
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [options, setOptions] = useState(['', '']);
  const [submitting, setSubmitting] = useState(false);

  const addOption = () => {
    if (options.length < 6) {
      setOptions([...options, '']);
    }
  };

  const updateOption = (index: number, value: string) => {
    const updated = options.map((opt, i) => (i === index ? value : opt));
    setOptions(updated);
  };

  const removeOption = (index: number) => {
    if (options.length > 2) {
      setOptions(options.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async () => {
    const validOptions = options.filter((o) => o.trim());
    if (!title.trim() || validOptions.length < 2) {
      alert('请输入标题和至少两个选项');
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch('/api/debates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          options: validOptions,
        }),
      });

      if (res.ok) {
        setTitle('');
        setDescription('');
        setOptions(['', '']);
        setOpen(false);
        onCreated();
      } else {
        const err = await res.json();
        alert(err.error || '创建失败');
      }
    } catch {
      alert('网络错误');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full py-3 border border-dashed border-[#D3D3D3] rounded-lg text-[#8590A6] hover:border-[#0066FF] hover:text-[#0066FF] transition-colors text-sm bg-white"
      >
        + 自定义辩题
      </button>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-[#EBEBEB] p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-[#1A1A1A] text-[15px]">发起新辩题</h3>
        <button onClick={() => setOpen(false)} className="text-[#8590A6] hover:text-[#1A1A1A] text-sm">
          取消
        </button>
      </div>

      <input
        type="text"
        placeholder="辩题标题（如：AI 会在 2026 年取代程序员吗？）"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full px-3 py-2.5 border border-[#EBEBEB] rounded text-sm focus:outline-none focus:border-[#0066FF] text-[#1A1A1A] placeholder:text-[#C8C8C8]"
      />

      <textarea
        placeholder="补充描述（可选）"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={2}
        className="w-full px-3 py-2.5 border border-[#EBEBEB] rounded text-sm focus:outline-none focus:border-[#0066FF] text-[#1A1A1A] placeholder:text-[#C8C8C8] resize-none"
      />

      <div className="space-y-2">
        <label className="text-sm text-[#646464]">选项（至少两个）</label>
        {options.map((opt, i) => (
          <div key={i} className="flex gap-2">
            <input
              type="text"
              placeholder={`选项 ${i + 1}`}
              value={opt}
              onChange={(e) => updateOption(i, e.target.value)}
              className="flex-1 px-3 py-2 border border-[#EBEBEB] rounded text-sm focus:outline-none focus:border-[#0066FF] text-[#1A1A1A] placeholder:text-[#C8C8C8]"
            />
            {options.length > 2 && (
              <button onClick={() => removeOption(i)} className="px-2 text-[#8590A6] hover:text-[#F1403C] text-sm">
                删除
              </button>
            )}
          </div>
        ))}
        {options.length < 6 && (
          <button onClick={addOption} className="text-sm text-[#0066FF] hover:text-[#0052CC]">
            + 添加选项
          </button>
        )}
      </div>

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="w-full py-2.5 bg-[#0066FF] text-white rounded text-sm font-medium hover:bg-[#0052CC] disabled:opacity-50 transition-colors"
      >
        {submitting ? '创建中...' : '创建辩题'}
      </button>
    </div>
  );
}
