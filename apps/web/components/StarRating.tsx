import { useState } from "react";
import { Star } from "lucide-react";

interface StarRatingProps {
  rating: number; // Current rating value
  onRatingChange: (value: number) => void; // Function to handle rating changes
}

export function StarRating({ rating, onRatingChange }: StarRatingProps) {
  const [hover, setHover] = useState<number | null>(null); // Hovered star index

  return (
    <div className="flex">
      {[...Array(5)].map((_, index) => {
        const ratingValue = index + 1;

        return (
          <label key={index}>
            <input
              type="radio"
              name="rating"
              value={ratingValue}
              onClick={() => onRatingChange(ratingValue)}
              className="hidden"
            />
            <Star
              className={`cursor-pointer transition-colors ${
                ratingValue <= (hover || rating) ? "text-blue-400" : "text-gray-300"
              }`}
              size={24}
              onMouseEnter={() => setHover(ratingValue)}
              onMouseLeave={() => setHover(null)}
            />
          </label>
        );
      })}
    </div>
  );
}
