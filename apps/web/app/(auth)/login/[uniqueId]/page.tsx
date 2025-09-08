"use client";
 
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { useRouter, useParams } from "next/navigation";
import Image from "next/image";
import images from "@/images/Interview.jpg";
import Jman_img from "@/images/JmanLogo.png";
 
const loginSchema = z.object({
  email: z
    .string()
    .nonempty({ message: "Email is required" })
    .email("Invalid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});
 
export default function CandidateLoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isValid, setIsValid] = useState(false); // To track uniqueId validity
  const { toast } = useToast();
  const router = useRouter();
  const { uniqueId } = useParams(); // Extract uniqueId from URL
 
  const form = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });
 
  useEffect(() => {
    async function validateUniqueId() {
      try {
        const response = await fetch(`/api/validate-link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uniqueId }),
        });
        if (!response.ok) {
          router.push("/404");
        } else {
          setIsValid(true);
        }
      } catch (error) {
        console.error("Error validating uniqueId:", error);
        router.push("/404");
      }
    }
 
    if (uniqueId) {
      validateUniqueId();
    }
  }, [uniqueId, router]);
 
  async function onSubmit(values: z.infer<typeof loginSchema>) {
    try {
      setIsLoading(true);
 
      const response = await fetch(`/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...values, uniqueId }),
      });
 
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Login failed");
      }
 
      router.push(data.redirect);
      toast({
        title: "Success",
        description: "Logged in successfully",
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Invalid credentials";
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  }
 
  if (!isValid) {
    return null; // Optionally show a loader while validating
  }
 
  return (
    <div className="min-h-screen flex">
      {/* Left Side: Login Form */}
      <div className="flex-1 flex items-center justify-center bg-card">
        <div className="absolute top-4 left-4 flex items-center space-x-2">
          <Image
            src={Jman_img}
            alt="Company Logo"
            width={25}
            height={14}
            className="object-contain"
          />
          <span className="text-md font-bold text-primary">JMAN Group</span>
        </div>
        <div className="w-full max-w-sm p-6 space-y-6 bg-white rounded-lg">
          <div className="flex flex-col items-center space-y-2">
            <h2 className="text-xl font-semibold">Welcome to JHire</h2>
            <p className="text-xs text-muted-foreground">Sign in to your account</p>
          </div>
 
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-4"
              autoComplete="off"
            >
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email address</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Your Email"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage className="text-xs" />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        autoComplete="off"
                        {...field}
                        className="h-8 text-sm px-2"
                      />
                    </FormControl>
                    <FormMessage className="text-xs" />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                className="w-full h-8 text-sm"
                disabled={isLoading}
              >
                {isLoading ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          </Form>
        </div>
      </div>
 
      {/* Right Side: Image */}
      <div className="flex-1 relative hidden md:block">
        <Image
          src={images}
          alt="Login Illustration"
          layout="fill"
          objectFit="cover"
          priority
        />
      </div>
    </div>
  );
}