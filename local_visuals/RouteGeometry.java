// SPDX-License-Identifier: GPL-3.0-only
import java.io.*;
import java.util.*;
import net.osmand.binary.*;
import net.osmand.router.*;
import net.osmand.data.LatLon;
class RouteGeometry {
 public static void main(String[] a)throws Exception {
  File f=new File(a[0]); BinaryMapIndexReader reader=new BinaryMapIndexReader(new RandomAccessFile(f,"r"),f); try{
   double x=Double.parseDouble(a[1]),y=Double.parseDouble(a[2]),u=Double.parseDouble(a[3]),v=Double.parseDouble(a[4]);
   RouteResultPreparation.PRINT_TO_CONSOLE_ROUTE_INFORMATION=true;
   RouteResultPreparation.PRINT_TO_CONSOLE_ROUTE_INFORMATION_TO_TEST=true;
   var cfg=RoutingConfiguration.getDefault().build("car",new RoutingConfiguration.RoutingMemoryLimits(TestRouting.MEMORY_TEST_LIMIT,TestRouting.NATIVE_MEMORY_TEST_LIMIT));
   var front=new RoutePlannerFrontEnd(); var readers=new BinaryMapIndexReader[]{reader};
   var ctx=front.buildRoutingContext(cfg,null,readers);
   if(front.findRouteSegment(x,y,ctx,null)==null || front.findRouteSegment(u,v,ctx,null)==null)throw new IOException("No snapped endpoint");
   ctx=front.buildRoutingContext(cfg,null,readers);
   var result=front.searchRoute(ctx,new LatLon(x,y),new LatLon(u,v),null);
   if(!result.isCorrect())throw new IOException("Route failed");
   var segments=result.getList();System.out.println("Route is "+segments.size()+" segments");
   int count=0,seg=0;
   for(var s:segments){
    int start=s.getStartPointIndex(),end=s.getEndPointIndex(),step=start<=end?1:-1;
    System.out.println("GEOMSEG\t"+seg+"\t"+s.getObject().getId()+"\t"+start+"\t"+end);
    for(int i=start;;i+=step){if(++count>100000)throw new IOException("Point bound");var p=s.getPoint(i);System.out.println("POINT\t"+seg+"\t"+i+"\t"+p.getLatitude()+"\t"+p.getLongitude());if(i==end)break;}seg++;
   }
  } finally {reader.close();}
 }
}
